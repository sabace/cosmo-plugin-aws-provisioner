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

    def test_instance_create_and_delete(self):

        ec2_client = self.get_ec2_client()
        name = self.name_prefix + 'inst_crt_del'
        tst_inst_cfg = tests_config['instance']
        tst_sg_cfg = tests_config['security_group']
        ctx = MockCloudifyContext(
            node_id='__cloudify_id_' + name,
            properties={
                'instance': {
                    'Name': name,
                    'image_id': tst_inst_cfg['image_id'],
                    'placement': tst_inst_cfg['placement'],
                    'instance_type': tst_inst_cfg['instance_type'],
                    'security_groups': tst_inst_cfg['security_groups'],
                    'key_name': tst_inst_cfg['key_name']
                },
                'security_group': {
                    'crt_sg_name': tst_sg_cfg['create']['crt_sg_name'],
                    'description': tst_sg_cfg['create']['description'],
                    'del_sg_name': tst_sg_cfg['delete']['del_sg_name'],
                    'conf_sg_name': tst_sg_cfg['configure']['conf_sg_name'],
                    'ip_protocol': tst_sg_cfg['configure']['ip_protocol'],
                    "cidr_ip": tst_sg_cfg['configure']['cidr_ip'],
                    "from_port": tst_sg_cfg['configure']['from_port'],
                    "to_port": tst_sg_cfg['configure']['to_port']
                },
            }
        )

        # Test: create
        #self.assertThereIsNoServer(name=name)
        cfy_srv.launch_new_instance(ctx,ec2_client)
        #cfy_srv.get_server_by_context(ec2_client,ctx)
        #cfy_srv.create_security_group(ctx)
        #cfy_srv.delete_security_group(ctx)
        #cfy_srv.configure_security_group(ctx)
        #self.assertThereIsOneServer(name=name)

        #cfy_srv.start(ctx)
        #cfy_srv.stop(ctx)
        #cfy_srv.delete(ctx)

        #self.assertThereIsNoServer()


if __name__ == '__main__':
    unittest.main()
    # _mock_start_monitor(object())
