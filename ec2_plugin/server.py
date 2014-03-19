#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import time
import copy
import inspect
import itertools
import aws_plugin_common
from base64 import standard_b64decode

from cloudify.decorators import operation

with_ec2_client = aws_plugin_common.with_ec2_client

NODE_ID_PROPERTY = 'cloudify_id'
AWS_SERVER_ID_PROPERTY = 'aws_instance_id'
sec_group = {}


def launch_new_instance(ctx, ec2_client):
    """
    Creates a instance. Exposes the parameters mentioned in
    http://boto.readthedocs.org/en/latest/ref/ec2.html#module-boto.ec2
    run_instances class
    """
    # For possible changes by _maybe_transform_userdata()

    instance = {
        'Name': ctx.node_id
    }
    instance.update(copy.deepcopy(ctx.properties['instance']))

    ctx.logger.debug(
        "instance.run_instances() server before transformations: {0}".format(instance))

    ctx.logger.debug(
        "instance.run_instances() VM after transformations: {0}".format(instance))

    # First parameter is 'self', skipping
    params_names = inspect.getargspec(ec2_client.run_instances).args[2:]

    params_default_values = inspect.getargspec(
        ec2_client.run_instances).defaults
    params = dict(itertools.izip(params_names, params_default_values))

    # Sugar
    if 'image_id' in instance:
        instance['image_id'] = ec2_client.get_all_images(image_ids=instance['image_id'])
        params['image_id'] = instance['image_id'][0].id
        del instance['image_id']

    tag_name = instance['Name']
    del instance['Name']

    # Fail on unsupported parameters
    for k in instance:
        if k not in params:
            raise ValueError("Parameter with name '{0}' must not be passed to"
                             " AWS provisioner (under host's "
                             "properties.ec2.instance)".format(k))

    for k in params:
        if k in instance:
            params[k] = instance[k]

    if not params['user_data']:
        params['user_data'] = dict({})
    params['user_data'][NODE_ID_PROPERTY] = ctx.node_id
    params['user_data'] = params['user_data']['cloudify_id']
    security_group_presence = _get_security_group_by_name(ec2_client,
                                                          instance['security_groups'])

    sg = []
    if security_group_presence[0]['name'] == instance['security_groups']:
        sg.append(instance['security_groups'])
        params['security_groups'] = sg
    else:
        sg.append(create_security_group(ctx))
        params['security_groups'] = sg

    ctx.logger.debug(
        "Asking EC2 to create Instance. All possible parameters are: {0})"
        .format(','.join(params.keys())))
    try:
        server = ec2_client.run_instances(**params)

        active_instance = _wait_for_server_to_become_active(ec2_client, server)
        ##Assign name to server
        ec2_client.create_tags([active_instance.id], {"Name": tag_name})

        instance_details = _get_instance_status(ec2_client, active_instance.id)
        ctx.logger.info("Created VM with Parameters {0} Security_Group {1}."
                        .format(str(instance_details),
                                params['security_groups']))

    except Exception as e:
        raise RuntimeError("Boto bad request error: " + str(e))
    ctx[AWS_SERVER_ID_PROPERTY] = active_instance.id
    ctx.update()


@operation
@with_ec2_client
def start(ctx, ec2_client, **kwargs):
    """
    Start instance.

    Depends on AWS implementation
    """
    instance = get_server_by_context(ec2_client, ctx)
    if instance is not None:
        ec2_client.start_instances(instance)
        return

    launch_new_instance(ctx, ec2_client)


@operation
@with_ec2_client
def stop(ctx, ec2_client, **kwargs):
    """
    Stop Instance.

    Depends on AWS implementation
    """
    instance = get_server_by_context(ec2_client, ctx)
    instance_state = _get_instance_status(ec2_client, instance)
    if instance_state[0]['Status'] is "running":
        ec2_client.stop_instances(instance)
    else:
        raise RuntimeError(
            "Cannot stop instance - server doesn't exist for node: {0}"
            .format(ctx.node_id))


@operation
@with_ec2_client
def delete(ctx, ec2_client, **kwargs):
    """
    Terminates Instance in ctx.

    Depends on AWS implementation
    """
    instance = get_server_by_context(ec2_client, ctx)
    instance_state = _get_instance_status(ec2_client, instance)
    if instance_state[0]['Status'] is "running" or \
            instance[0]['Status'] is "stopped":
        ec2_client.terminate_instances(instance)
    else:
        raise RuntimeError(
            "Cannot delete server - server doesn't exist for node: {0}"
            .format(ctx.node_id))


def get_server_by_context(ec2_client, ctx):
    """
    Gets a instance for the provided context.

    If aws instance id is present it would be used for getting the server.
    Otherwise, an iteration on all servers userdata will be made.
    """
    # Getting instance by its AWS instance id is faster tho it requires
    # a REST API call to Cloudify's storage for getting runtime properties.
    if AWS_SERVER_ID_PROPERTY in ctx:
        reservations = ec2_client.get_all_instances(instance_ids=ctx[AWS_SERVER_ID_PROPERTY])
        instances = [i for r in reservations for i in r.instances]
        return instances[0].id
    # Fallback
    reservations = ec2_client.get_all_instances()
    instances = [i for r in reservations for i in r.instances]
    for instance in instances:
        usr_data = ec2_client.get_instance_attribute(instance.id, 'userData')
        if usr_data['userData'] is not None:
            encoded_userdata = standard_b64decode(usr_data['userData'])
            if NODE_ID_PROPERTY in encoded_userdata:
                return instance.id
    return None


@operation
@with_ec2_client
def create_security_group(ctx, ec2_client, **kwargs):

    #Creates Security Group
    sec_group.update(copy.deepcopy(ctx.properties['security_group']))
    security_group_presence = _get_security_group_by_name(ec2_client,
                                                          sec_group['crt_sg_name'])
    if security_group_presence:
        raise RuntimeError("Security Group name '{0}' is already Used."
                           .format(sec_group['crt_sg_name']))
    else:
        sg_create = ec2_client.create_security_group(
            sec_group['crt_sg_name'],
            sec_group['description'])
        ctx.logger.info("Creating Security Group with Parameters: {0}".format(str(sg_create)))
        return str(sg_create.name)


@operation
@with_ec2_client
def delete_security_group(ctx, ec2_client, **kwargs):

    #Deletes Security Group
    sec_group.update(copy.deepcopy(ctx.properties['security_group']))
    security_group_presence = _get_security_group_by_name(
        ec2_client,
        sec_group['del_sg_name'])
    if security_group_presence:
        try:
            ec2_client.delete_security_group(
                name=security_group_presence[0]['name'],
                group_id=security_group_presence[0]['id'])
            ctx.logger.info("Security group Deleted")
        except Exception as e:
            raise RuntimeError("Boto bad request error: " + str(e))
    else:
        raise RuntimeError(
            "Cannot delete Security Group - Security Group doesn't exist for node: {0}"
            .format(sec_group['del_sg_name']))


@operation
@with_ec2_client
def configure_security_group(ctx, ec2_client, **kwargs):

    #Add rules to existing Security Group
    sec_group.update(copy.deepcopy(ctx.properties['security_group']))
    print sec_group
    _fail_on_missing_required_parameters(sec_group, ('conf_sg_name',
                                                     'ip_protocol',
                                                     'cidr_ip',
                                                     'from_port',
                                                     'to_port', ),
                                         'security_groups.configure')
    security_group_presence = _get_security_group_by_name(ec2_client,
                                                          sec_group['conf_sg_name'])
    if security_group_presence:
        try:
            security_group = ec2_client.authorize_security_group(
                group_name=security_group_presence[0]['name'],
                src_security_group_group_id=security_group_presence[0]['id'],
                ip_protocol=sec_group['ip_protocol'],
                cidr_ip=sec_group['cidr_ip'],
                from_port=sec_group['from_port'],
                to_port=sec_group['to_port'])
            ctx.logger.info("Rules added to the Security group ")
        except Exception as e:
            raise RuntimeError("Boto bad request error: " + str(e))
    else:
        raise RuntimeError(
            "Unable to Add rules to the Group - Security Group doesn't exist for node: {0}"
            .format(sec_group['conf_sg_name']))


def _get_security_group_by_name(ec2_client, name):
    #Return Security Group Name is present or not in AWS EC2
    security_groups = ec2_client.get_all_security_groups(groupnames=None,
                                                         group_ids=None,
                                                         filters=None)
    return [{'id': sg.id, "name": sg.name} for sg in security_groups if sg.name == name]


def _get_instance_status(ec2_client, instance_id):
    #Instance Status in AWS
    aws_reservations = ec2_client.get_all_instances()
    instances = [i for r in aws_reservations for i in r.instances]
    for i in instances:
        if i.id == instance_id:
            return [{"Status": i.update(), "Host_name": i.tags["Name"],
                    "Image Id": i.image_id, "Placement": i.placement,
                    "Key_Name": i.key_name, "Public IP": i.ip_address,
                    "Hardware id": instance_id, "Private IP": i.private_ip_address}]


def _wait_for_server_to_become_active(ec2_client, instance):
    timeout = 100
    while instance.instances[0].state != "running":
        timeout -= 5
        if timeout <= 0:
            raise RuntimeError('Server failed to start in time')
        time.sleep(5)
        instance = ec2_client.get_all_instances(instance_ids=str(instance.instances[0].id))[0]

    return instance.instances[0]


def _fail_on_missing_required_parameters(obj, required_parameters, hint_where):
    for k in required_parameters:
        if k not in obj:
            raise ValueError(
                "Required parameter '{0}' is missing (under host's "
                "properties.{1}). Required parameters are: {2}"
                .format(k, hint_where, required_parameters))

