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

from cloudify.decorators import operation

with_ec2_client = aws_plugin_common.with_ec2_client

NODE_ID_PROPERTY = 'cloudify_id'
AWS_INSTANCE_ID_PROPERTY = 'aws_instance_id'


def start_new_instance(ctx, ec2_client):
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

    _maybe_transform_userdata(instance)


    #_fail_on_missing_required_parameters(
    #    instance,
    #    ('image_id','instance_type', 'placement', 'user_data', 'key_name'),
    #    'instance')

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
        params['image_id'] =  instance['image_id'][0].id
        del instance['image_id']

    server_name = instance['Name']
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


#    if not params['meta']:
#        params['meta'] = dict({})
#    params['meta'][NODE_ID_PROPERTY] = ctx.node_id

    #ctx.logger.info("Creating VM with parameters: {0}".format(str(params)))
    ctx.logger.debug(
        "Asking EC2 to create Instance. All possible parameters are: {0})"
        .format(','.join(params.keys())))
    try:
        server = ec2_client.run_instances(**params)

        active_instance = _wait_for_server_to_become_active(ec2_client, server)
        ##Assign name to server
        ec2_client.create_tags([active_instance.id], {"Name": server_name})

        instance_details = _get_instance_status(ec2_client,active_instance.id)
        ctx.logger.info("Created VM with Parameters {0}.".format(str(instance_details)))

    except Exception as e:
        raise RuntimeError("Boto bad request error: " + str(e))
    ctx[AWS_INSTANCE_ID_PROPERTY] = active_instance.id


@operation
@with_ec2_client
def start(ctx, ec2_client, **kwargs):

    #Start an Instance if it's stopped
    _fail_on_missing_required_parameters(kwargs, ('instance_id',),
                                         'User parameters')
    instance_presence = _get_instances_by_instance_id(
        ec2_client,
        kwargs['instance_id'])
    if instance_presence:
        ec2_client.start_instances(kwargs['instance_id'])
        instance_state = _get_instance_status(ec2_client,kwargs['instance_id'])
        ctx.logger.info ("VM Details ".format(str(instance_state)))
    else:
        raise RuntimeError(
            "Cannot start server - server doesn't exist for node: {0}"
            .format(ctx.node_id))


@operation
@with_ec2_client
def stop(ctx, ec2_client, **kwargs):

    #To Stop an Instance if it's running state
    _fail_on_missing_required_parameters(kwargs, ('instance_id',),
                                         'User parameters')
    instance_presence = _get_instances_by_instance_id(
        ec2_client,
        kwargs['instance_id'])
    if instance_presence:
        ec2_client.stop_instances(kwargs['instance_id'])
        instance_state = _get_instance_status(ec2_client,kwargs['instance_id'])
        ctx.logger.info ("VM Details ".format(str(instance_state)))
    else:
        raise RuntimeError(
            "Cannot stop server - server doesn't exist for node: {0}"
            .format(ctx.node_id))


@operation
@with_ec2_client
def delete(ctx, ec2_client, **kwargs):

    #To Delete Instance
    _fail_on_missing_required_parameters(kwargs, ('instance_id',),
                                         'User parameters')
    instance_presence = _get_instances_by_instance_id(
        ec2_client,
        kwargs['instance_id'])
    if instance_presence:
        ec2_client.terminate_instances(kwargs['instance_id'])
        ctx.logger.info("Server Deleted from EC2")
    else:
        raise RuntimeError(
            "Cannot delete server - server doesn't exist for node: {0}"
            .format(ctx.node_id))


@operation
@with_ec2_client
def create_security_group(ctx, ec2_client, **kwargs):

    #To Create Security Group
    _fail_on_missing_required_parameters(kwargs, ('name', 'description', ),
                                         'User parameters')
    security_group_presence = _get_security_group_by_name(ec2_client,
                                                          kwargs['name'])
    if security_group_presence:
        raise RuntimeError("Security Group name '{0}' is already Used."
                           .format(kwargs['name']))
    else:
        security_group = ec2_client.create_security_group(
            kwargs['name'],
            kwargs['description'])
        ctx.logger.info("Creating Security Group with Parameters: {0}".format(str(security_group)))
        return security_group


@operation
@with_ec2_client
def delete_security_group(ctx, ec2_client, **kwargs):

    #To delete Security Group
    _fail_on_missing_required_parameters(kwargs, ('name', 'group_id', ),
                                         'User parameters')
    security_group_presence = _get_security_group_by_name(
        ec2_client,
        kwargs['name'])
    if security_group_presence:
        deleted_security_group = ec2_client.delete_security_group(
            name=kwargs['name'],
            group_id=kwargs['group_id'])
        return deleted_security_group
    else:
        raise RuntimeError(
            "Cannot delete Security Group - Security Group doesn't exist for node: {0}"
            .format(ctx.node_id))


@operation
@with_ec2_client
def configure_security_group(ctx, ec2_client, **kwargs):

    #To Add rules to existing Security Group
    _fail_on_missing_required_parameters(kwargs, ('name',
                                                  'source_group_id',
                                                  'ip_protocol',
                                                  'cidr_ip',
                                                  'from_port',
                                                  'to_port', ),
                                         'User parameters')
    security_group_presence = _get_security_group_by_name(ec2_client,
                                                          kwargs['name'])
    if security_group_presence:
        security_group = ec2_client.authorize_security_group(
            group_name=kwargs["name"],
            src_security_group_group_id=kwargs["source_group_id"],
            ip_protocol=kwargs['ip_protocol'],
            cidr_ip=kwargs['cidr_ip'],
            from_port=kwargs['from_port'],
            to_port=kwargs['to_port'])
        return security_group
    else:
        raise RuntimeError(
            "Unable to Add rules to the Group - Security Group doesn't exist for node: {0}"
            .format(ctx.node_id))


@operation
@with_ec2_client
def reconfigure_security_group(ctx, ec2_client, **kwargs):

    #To Delete rules in existing Security Group
    _fail_on_missing_required_parameters(kwargs, ('name',
                                                  'source_group_id',
                                                  'ip_protocol',
                                                  'cidr_ip', ),
                                         'User parameters')
    check_security_group = _get_security_group_by_name(ec2_client,
                                                       kwargs['name'])
    if kwargs['name'] not in check_security_group:
        modify_security_group_rule = ec2_client.revoke_security_group(
            group_name=kwargs["name"],
            src_security_group_group_id=kwargs["source_group_id"],
            ip_protocol=kwargs['ip_protocol'],
            cidr_ip=kwargs['cidr_ip'],
            from_port=kwargs['from_port'],
            to_port=kwargs['to_port'])
        return modify_security_group_rule
    else:
        raise RuntimeError(
            "Unable to Delete Rule - Rule doesn't exist for node: {0}"
            .format(ctx.node_id))


def _get_security_group_by_name(ec2_client, name):
    #Return Security Group Name is present or not in AWS EC2
    security_groups = ec2_client.get_all_security_groups(groupnames=None,
                                                         group_ids=None,
                                                         filters=None)
    return [{'name': sg.name} for sg in security_groups if sg.name == name]


def _get_instances_by_instance_id(ec2_client, instance_id):
    #Return Instance ID is present in AWS EC2
    reservations = ec2_client.get_all_instances()
    instances = [i for r in reservations for i in r.instances]
    for instance in instances:
        if instance.id == instance_id:
            return instance
    else:
        raise RuntimeError("Lookup of instances by id failed."
                           " There are {0} instances named '{1}'"
                           .format(instance_id), instance_id)


def _get_instance_status(ec2_client, instance_id):
    #Instance Status in AWS
    aws_reservations = ec2_client.get_all_instances()
    instances = [i for r in aws_reservations for i in r.instances]
    for i in instances:
        if i.id == instance_id:
            return [{"Status": i.update(), "Host_name": i.tags["Name"],
                    "Image Id": i.image_id, "Placement": i.placement,
                    "Security_Group": i.key_name, "Public IP": i.ip_address,
                    "Hardware id": instance_id, "Private IP": i.private_ip_address}]


def _wait_for_server_to_become_active(ec2_client, server):
    timeout = 100
    while server.instances[0].state != "running":
        timeout -= 5
        if timeout <= 0:
            raise RuntimeError('Server failed to start in time')
        time.sleep(5)
        server = ec2_client.get_all_instances(instance_ids=str(server.instances[0].id))[0]

    return server.instances[0]


def _fail_on_missing_required_parameters(obj, required_parameters, hint_where):
    for k in required_parameters:
        if k not in obj:
            raise ValueError(
                "Required parameter '{0}' is missing (under host's "
                "properties.{1}). Required parameters are: {2}"
                .format(k, hint_where, required_parameters))


# *** userdata handling - start ***
userdata_handlers = {}


def userdata_handler(type_):
    def f(x):
        userdata_handlers[type_] = x
        return x
    return f


def _maybe_transform_userdata(nova_config_instance):
    """Allows userdata to be read from a file, etc, not just be a string"""
    if 'userdata' not in nova_config_instance:
        return
    if not isinstance(nova_config_instance['userdata'], dict):
        return
    ud = nova_config_instance['userdata']

    _fail_on_missing_required_parameters(
        ud,
        ('type',),
        'server.userdata')

    if ud['type'] not in userdata_handlers:
        raise ValueError("Invalid type '{0}' (under host's "
                         "properties.nova_config.instance.userdata)"
                         .format(ud['type']))

    nova_config_instance['userdata'] = userdata_handlers[ud['type']](ud)

# *** userdata handling - end ***