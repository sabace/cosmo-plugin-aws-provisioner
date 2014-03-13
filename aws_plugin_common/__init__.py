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
import unittest
import logging
import string
from functools import wraps
import json
import random
import os

import boto.ec2 as aws_client

import cloudify.manager
import cloudify.decorators

PREFIX_RANDOM_CHARS = 3
CLEANUP_RETRIES = 10
CLEANUP_RETRY_SLEEP = 2


class Config(object):
    def get(self):
        which = self.__class__.which
        env_name = which.upper() + '_CONFIG_PATH'
        default_location_tpl = '~/' + which + '_config.json'
        default_location = os.path.expanduser(default_location_tpl)
        config_path = os.getenv(env_name, default_location)
        try:
            with open(config_path) as f:
                cfg = json.loads(f.read())
        except IOError:
            raise RuntimeError(
                "Failed to read {0} configuration from file '{1}'."
                "The configuration is looked up in {2}. If defined, "
                "environment variable "
                "{3} overrides that location.".format(
                    which, config_path, default_location_tpl, env_name))
        return cfg


class EC2Config(Config):
    which = 'ec2'


class TestsConfig(Config):
    which = 'os_tests'


class AwsClient(object):
    def get(self, config=None, *args, **kw):
        static_config = self.__class__.config().get()
        cfg = {}
        cfg.update(static_config)
        if config:
            cfg.update(config)
        ret = self.connect(cfg, *args, **kw)
        ret.format = 'json'
        return ret


# Clients acquireres

class EC2Client(AwsClient):

    config = EC2Config

    def connect(self, cfg):
        return aws_client.connect_to_region(
            aws_access_key_id=cfg['Amazon Credentials']['aws_access_key_id'],
            aws_secret_access_key=cfg['Amazon Credentials']['aws_secret_access_key'],
            region_name=cfg['Amazon Credentials']['region'])


# Decorators

def _find_instanceof_in_kw(cls, kw):
    ret = [v for v in kw.values() if isinstance(v, cls)]
    if not ret:
        return None
    if len(ret) > 1:
        raise RuntimeError(
            "Expected to find exactly one instance of {0} in "
            "kwargs but found {1}".format(cls, len(ret)))
    return ret[0]


def _find_context_in_kw(kw):
    return _find_instanceof_in_kw(cloudify.context.CloudifyContext, kw)


def with_ec2_client(f):
    @wraps(f)
    def wrapper(*args, **kw):
        ctx = _find_context_in_kw(kw)
        if ctx:
            config = ctx.properties.get('ec2_config')
        else:
            config = None
        ec2_client = EC2Client().get(config=config)
        kw['ec2_client'] = ec2_client
        return f(*args, **kw)
    return wrapper

#TestCases

class TestCase(unittest.TestCase):

    def get_ec2_client(self):
        r = EC2Client().get()
        self.get_ec2_client = lambda: r
        return self.get_ec2_client()

    def _mock_send_event(self, *args, **kw):
        self.logger.debug("_mock_send_event(args={0}, kw={1})".format(
            args, kw))

    def _mock_get_node_state(self, __cloudify_id, *args, **kw):
        self.logger.debug(
            "_mock_get_node_state(__cloudify_id={0} args={1}, kw={2})".format(
                __cloudify_id, args, kw))
        return self.nodes_data[__cloudify_id]

    def setUp(self):
        # Careful!
        logger = logging.getLogger(__name__)
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logger
        self.logger.level = logging.DEBUG
        self.logger.debug("Cosmo test setUp() called")
        chars = string.ascii_uppercase + string.digits
        self.name_prefix = 'cosmo_test_{0}_'\
            .format(''.join(
                random.choice(chars) for x in range(PREFIX_RANDOM_CHARS)))
        self.timeout = 120

        self.logger.debug("Cosmo test setUp() done")

    @with_ec2_client
    def assertThereIsOneServerAndGet(self, ec2_client, **kw):
        instances = ec2_client.get_all_instances()
        instances = [i for r in instances for i in r.instances]
        self.assertEquals(1, len(instances[0].tags['Name']))
        return instances[0].tags['Name']

    assertThereIsOneServer = assertThereIsOneServerAndGet

    @with_ec2_client
    def assertThereIsNoServer(self, ec2_client, **kw):
        tags = ec2_client.get_all_tags()
        #instances = [i for r in tags for i in r.instances]
        for tag in tags:
            if tag.name == 'Name':
                if tag.value == kw['name']:
                    self.assertEquals(0, len(tag.value))

