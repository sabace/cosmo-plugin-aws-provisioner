###############################################################################
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved         #
#                                                                             #
# Licensed under the Apache License, Version 2.0 (the "License");             #
# you may not use this file except in compliance with the License.            #
# You may obtain a copy of the License at                                     #
#                                                                             #
# http://www.apache.org/licenses/LICENSE-2.0                                  #
#                                                                             #
# Unless required by applicable law or agreed to in writing, software         #
# distributed under the License is distributed on an "AS IS" BASIS,           #
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  #
# * See the License for the specific language governing permissions and       #
# * limitations under the License.                                            #
###############################################################################

import os
import json
import copy
import inspect
import itertools
from boto.ec2 import connect_to_region

from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


#@task
def provision(aws_config, **kwargs):

    """
    Creates a instance. Exposes the parameters mentioned in
    http://boto.readthedocs.org/en/latest/ref/ec2.html#module-boto.ec2
    run_instances class
    """
    config_path = _config(aws_config)
    instance_config = config_path["instance"]

    _fail_on_missing_required_parameters(kwargs, ('image_id',),
                                         'User Parameters')

    aws_instance = copy.deepcopy(instance_config)    # For possible changes by
    #  _maybe_transform_userdata()

    _maybe_transform_userdata(aws_instance)

    _fail_on_missing_required_parameters(aws_instance, ('instance_type',
                                                        'placement',
                                                        'user_data',
                                                        'key_name'),
                                         'aws_config.instance')

    aws_client = _init_client()

    params_names = inspect.getargspec(aws_client.run_instances).args[2:]

    params_default_values = inspect.getargspec(aws_client.run_instances).defaults
    params = dict(itertools.izip(params_names, params_default_values))

    # Fail on unsupported parameters
    for k in aws_instance:
        if k not in params:
            raise ValueError("Parameter with name '{0}' "
                             "must not be passed to aws provisioner "
                             "(under host's properties.aws.instance)"
                             .format(k))

    for k in params:
        if k in aws_instance:
            params[k] = aws_instance[k]

    params['image_id'] = kwargs['image_id']
    params['security_groups'] = [aws_instance["security_groups"]]

    logger.info("Asking Boto to create Instance. Parameters: {0}"
                .format(str(params)))
    logger.debug("Asking Boto to create Instance. All possible parameters are:"
                 " {0})".format(','.join(params.keys())))
    aws_client.run_instances(**params)


#@task
def start(aws_config, **kwargs):

    #Start an Instance if it's stopped
    aws_client = _init_client()
    _fail_on_missing_required_parameters(kwargs, ('instance_id',),
                                         'User parameters')
    instance_presence = _get_instance_by_instance_id_or_fail(
        aws_client,
        kwargs['instance_id'])
    if instance_presence:
        aws_client.start_instances(kwargs['instance_id'])
    else:
        raise RuntimeError("Instance id do not match with any instances,"
                           "Can not START this instance"
                           .format(kwargs['instance_id']))


#@task
def stop(aws_config, **kwargs):

    #To Stop an Instance if it's running state

    aws_client = _init_client()
    _fail_on_missing_required_parameters(kwargs, ('instance_id',),
                                         'User parameters')
    instance_presence = _get_instance_by_instance_id_or_fail(
        aws_client,
        kwargs['instance_id'])
    if instance_presence:
        aws_client.stop_instances(kwargs['instance_id'])
    else:
        raise RuntimeError("Instance id do not match with any instances"
                           ",Can not STOP this instance"
                           .format(kwargs['instance_id']))


#@task
def terminate(aws_config, **kwargs):

    #To Delete Instance
    aws_client = _init_client()
    _fail_on_missing_required_parameters(kwargs, ('instance_id',),
                                         'User parameters')
    instance_presence = _get_instance_by_instance_id_or_fail(
        aws_client,
        kwargs['instance_id'])
    if instance_presence:
        aws_client.terminate_instances(kwargs['instance_id'])
    else:
        raise RuntimeError("Instance id do not match with any instances,"
                           "Cant TERMINATE this instance"
                           .format(kwargs['instance_id']))


#@task
def create_security_group(aws_config, **kwargs):

    #To Create Security Group
    aws_client = _init_client()
    _fail_on_missing_required_parameters(kwargs, ('name', 'description', ),
                                         'User parameters')
    security_group_presence = _get_security_group_by_name(aws_client,
                                                          kwargs['name'])
    if security_group_presence:
        raise RuntimeError("Security Group name '{0}' is already Used."
                           .format(kwargs['name']))
    else:
        security_group = aws_client.create_security_group(
            kwargs['name'],
            kwargs['description'])
        return security_group


#@task
def delete_security_group(aws_config, **kwargs):

    #To delete Security Group
    aws_client = _init_client()
    _fail_on_missing_required_parameters(kwargs, ('name', 'group_id', ),
                                         'User parameters')
    security_group_presence = _get_security_group_by_name(
        aws_client,
        kwargs['name'])
    if security_group_presence:
        deleted_security_group = aws_client.delete_security_group(
            name=kwargs['name'],
            group_id=kwargs['group_id'])
        return deleted_security_group
    else:
        raise RuntimeError("Unable to delete security group, "
                           "Security Group doesn't exist")


#@task
def configure_security_group(aws_config, **kwargs):

    #To Configure Security Group
    aws_client = _init_client()
    _fail_on_missing_required_parameters(kwargs, ('name',
                                                  'source_group_id',
                                                  'ip_protocol',
                                                  'cidr_ip', ),
                                         'User parameters')
    security_group_presence = _get_security_group_by_name(aws_client,
                                                          kwargs['name'])
    if security_group_presence:
        security_group = aws_client.authorize_security_group(
            group_name=kwargs["name"],
            src_security_group_group_id=kwargs["source_group_id"],
            ip_protocol=kwargs['ip_protocol'],
            cidr_ip=kwargs['cidr_ip'],
            from_port=kwargs['from_port'],
            to_port=kwargs['to_port'])
        return security_group
    else:
        raise RuntimeError("Unable to Add Rules to the Security group,"
                           "Security Group doesn't exist")


#@task
def reconfigure_security_group(aws_config, **kwargs):

    #To Revoke Security Group
    aws_client = _init_client()
    _fail_on_missing_required_parameters(kwargs, ('name',
                                                  'source_group_id',
                                                  'ip_protocol',
                                                  'cidr_ip', ),
                                         'User parameters')
    check_security_group = _get_security_group_by_name(aws_client,
                                                       kwargs['name'])
    if kwargs['name'] not in check_security_group:
        modify_security_group_rule = aws_client.revoke_security_group(
            group_name=kwargs["name"],
            src_security_group_group_id=kwargs["source_group_id"],
            ip_protocol=kwargs['ip_protocol'],
            cidr_ip=kwargs['cidr_ip'],
            from_port=kwargs['from_port'],
            to_port=kwargs['to_port'])
        return modify_security_group_rule
    else:
        raise RuntimeError("Unable to reconfigure Security group,"
                           "Security Group doesn't exist")


def _init_client():

    #Aws Connection
    default_location_tpl = '~/aws_config.json'
    config_path = os.getenv('AWS_CONFIG_PATH',
                            os.path.expanduser(default_location_tpl))
    with open(config_path, 'r') as f:
        aws_config = json.loads(f.read())
    try:
        connection = connect_to_region(
            aws_access_key_id=aws_config["Amazon Credentials"]["aws_access_key_id"],
            aws_secret_access_key=aws_config["Amazon Credentials"]["aws_secret_access_key"],
            region_name=aws_config["Amazon Credentials"]["region"])
    except IOError:
        raise RuntimeError(
            "Failed to read {0} configuration from file '{1}'."
            .format(config_path, default_location_tpl))

    return connection


def _get_security_group_by_name(aws_client, name):
    #Return Security Group Name is present or not in AWS EC2
    security_groups = aws_client.get_all_security_groups(groupnames=None,
                                                         group_ids=None,
                                                         filters=None)
    return [{'name': sg.name} for sg in security_groups if sg.name == name]


def _get_instances_by_instance_id(aws_client, instance_id):
    #Return Instance ID is present in AWS EC2
    reservations = aws_client.get_all_instances()
    instances = [i for r in reservations for i in r.instances]
    for instance in instances:
        if instance.id == instance_id:
            return instance
    else:
        raise RuntimeError("Lookup of instances by id failed."
                           " There are {0} instances named '{1}'"
                           .format(instance_id), instance_id)


def _get_instance_by_instance_id_or_fail(aws_client, instance_id):
    instance = _get_instances_by_instance_id(aws_client, instance_id)
    if instance:
        return instance
    raise ValueError("Lookup of instance by name failed. "
                     "Could not find a instance with name {0}")


def _get_instance_status(aws_client, instance_id):
    #Instance Status in AWS
    aws_reservations = aws_client.get_all_instances()
    instances = [i for r in aws_reservations for i in r.instances]
    for i in instances:
        if i == instance_id:
            status = i.update()
            return status


def _fail_on_missing_required_parameters(obj, required_parameters, hint_where):
    for k in required_parameters:
        if k not in obj:
            raise ValueError("Required parameter '{0}' is missing "
                             "(under host's properties.{1}). "
                             "Required parameters are: {2}"
                             .format(k, hint_where, required_parameters))


def _config(path):
    config_path = os.getenv('AWS_CONFIG_PATH',
                            os.path.expanduser('~/aws_config.json'))
    with open(config_path, 'r') as f:
        aws_config = json.loads(f.read())
        return aws_config


# *** userdata handling - start ***
userdata_handlers = {}


def userdata_handler(type_):

    def f(x):
        userdata_handlers[type_] = x
        return x
    return f


def _maybe_transform_userdata(aws_config_instance):

    """Allows userdata to be read from a file, etc, not just be a string"""
    if 'userdata' not in aws_config_instance:
        return

    if not isinstance(aws_config_instance['userdata'], dict):
        return

    ud = aws_config_instance['userdata']

    _fail_on_missing_required_parameters(ud, ('type',),
                                         'aws_config.instance.userdata')

    if ud['type'] not in userdata_handlers:
        raise ValueError("Invalid type '{0}' "
                         "(under host's properties.aws_config.instance.userdata)"
                         .format(ud['type']))

    aws_config_instance['userdata'] = userdata_handlers[ud['type']](ud)

# *** userdata handling - end ***