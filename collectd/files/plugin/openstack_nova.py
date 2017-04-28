#!/usr/bin/python
# Copyright 2015 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Collectd plugin for getting statistics from Nova
if __name__ == '__main__':
    import collectd_fake as collectd
else:
    import collectd

import collectd_openstack as openstack
from itertools import groupby


PLUGIN_NAME = 'openstack_nova'
INTERVAL = openstack.INTERVAL
server_statuses = ('active', 'building', 'deleted', 'error',
                   'hard_reboot', 'migrating', 'password',
                   'paused', 'reboot', 'rebuild', 'rescued',
                   'resized', 'revert_resize', 'soft_deleted',
                   'stopped', 'suspended', 'unknown', 'verify_resize')


class NovaInstanceStatsPlugin(openstack.CollectdPlugin):
    """ Class to report the statistics on Nova instances.

        Number of instances broken down by state
    """
    def __init__(self, *args, **kwargs):
        super(NovaInstanceStatsPlugin, self).__init__(*args, **kwargs)
        self.plugin = PLUGIN_NAME
        self.interval = INTERVAL
        self.pagination_limit = 500
        self._cache = {}

    @staticmethod
    def gen_metric(name, nb, state):
        return {
            'plugin_instance': name,
            'values': nb,
            'meta': {
                'state': state,
                'discard_hostname': True,
            }
        }

    def itermetrics(self):
        server_details = self.get_objects('nova', 'servers',
                                          params={'all_tenants': 1},
                                          detail=True, since=True)

        for server in server_details:
            _id = server.get('id')
            status = server.get('status', 'unknown').lower()
            if status == 'deleted':
                try:
                    self.logger.debug(
                        'remove deleted instance {} from cache'.format(_id))
                    del self._cache[_id]
                except KeyError:
                    self.logger.warning(
                        'cannot find instance in cache {}'.format(_id))
            else:
                self._cache[_id] = status

        servers = sorted(self._cache.values())
        servers_status = {s: list(g) for s, g in groupby(servers)}
        for status in server_statuses:
            nb = len(servers_status.get(status, []))
            yield NovaInstanceStatsPlugin.gen_metric('instances',
                                                     nb,
                                                     status)


plugin = NovaInstanceStatsPlugin(collectd, PLUGIN_NAME,
                                 disable_check_metric=True)


def config_callback(conf):
    plugin.config_callback(conf)


def notification_callback(notification):
    plugin.notification_callback(notification)


def read_callback():
    plugin.conditional_read_callback()


if __name__ == '__main__':
    import time
    collectd.load_configuration(plugin)
    plugin.read_callback()
    collectd.info('Sleeping for {}s'.format(INTERVAL))
    time.sleep(INTERVAL)
    plugin.read_callback()
    plugin.shutdown_callback()
else:
    collectd.register_config(config_callback)
    collectd.register_notification(notification_callback)
    collectd.register_read(read_callback, INTERVAL)
