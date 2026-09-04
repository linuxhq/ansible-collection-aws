# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import ansible.plugins.loader as plugin_loader

# Initialize collection routing so lookup tests exercise real plugin option resolution.
plugin_loader.init_plugin_loader()
