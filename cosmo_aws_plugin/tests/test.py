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

import argparse
import time
import unittest

from cloudify.mocks import MockCloudifyContext

import aws_plugin_common as common

import cosmo_aws_plugin.server as cfy_srv

tests_config = common.TestsConfig().get()

DELETE_WAIT_START = 1
DELETE_WAIT_FACTOR = 2
DELETE_WAIT_COUNT = 6


# WIP - start
# Maybe this chunk will not be needed as monitoring
# will be done differently, probably as a (celery) task
class MockReporter(object):
    state = {}

    def start(self, node_id, _host):
        self.__class__.state[node_id] = 'started'

    def stop(self, node_id, _host):
        self.__class__.state[node_id] = 'stopped'

# WIP - end


class AWSEC2Test(common.TestCase):

    def test_server_create_and_delete(self):

        ec2_client = self.get_ec2_client()
        name = self.name_prefix + 'srv_crt_del'
        ctx = MockCloudifyContext(
            node_id='__cloudify_id_' + name,
            properties={
                'instance': {
                    'Name': name,
                    'image_id' : tests_config['instance']['image_id'],
                    'placement': tests_config['instance']['placement'],
                    'user_data': tests_config['instance']['user_data'],
                    'instance_type': tests_config['instance']['instance_type'],
                    'key_name': tests_config['instance']['key_name'],
                },
            }
        )

        # Test: create
        ###self.assertThereIsNoServer(name=name)
        #cfy_srv.start_new_instance(ctx,ec2_client)
        ###self.assertThereIsOneServer(name=name)

        # WIP # # Test: start
        # WIP # cfy_srv.start(ctx)

        # WIP # # Test: stop
        # WIP # cfy_srv.stop(ctx)

        # Test: delete
        cfy_srv.delete(ctx,instance_id='xxxxxxxx')

        #self.assertThereIsNoServer()


if __name__ == '__main__':
    unittest.main()
    # _mock_start_monitor(object())
