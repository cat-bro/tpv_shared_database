import os
import oyaml as yaml
from bioblend.galaxy import GalaxyInstance

# os.system(f'rm {eu_destinations_file} ||:')
# os.system(f'wget {eu_destinations_url}')

eu_destinations_file = 'tool_destinations.yaml'
eu_destinations_url = 'https://raw.githubusercontent.com/usegalaxy-eu/infrastructure-playbook/master/files/galaxy/dynamic_rules/usegalaxy/tool_destinations.yaml'
eu_galaxy_url = 'https://usegalaxy.eu'

def get_short_id(tool_id):
    if '/' in tool_id:
        return tool_id.split('/')[-2]
    else:
        return tool_id

def convert_tool_id_to_tpv_regex(tool_id):
    if '/' in tool_id:
        return f'{("/").join(tool_id.split("/")[:-1])}/.*'
    else:
        return tool_id

def map_entry(key, tool_dests):
    entry = tool_dests[key]
    entry_unmapped_keys = list(entry.keys())
    new_entry = {}
    if 'cores' in entry_unmapped_keys:
        new_entry['cores'] = entry['cores']
        entry_unmapped_keys.remove('cores')
    if 'mem' in entry_unmapped_keys:
        new_entry['mem'] = entry['mem']
        entry_unmapped_keys.remove('mem')
    if 'gpus' in entry_unmapped_keys:
        new_entry['gpus'] = entry['gpus']
        entry_unmapped_keys.remove('gpus')
    if 'env' in entry_unmapped_keys:
        new_entry['env'] = entry['env']
        entry_unmapped_keys.remove('env')
    if 'runner' in entry_unmapped_keys:
        new_entry['scheduling'] = {}
        new_entry['scheduling']['require'] = [entry['runner']]
        entry_unmapped_keys.remove('runner')
    if 'params' in entry_unmapped_keys:
        new_entry['params'] = entry['params'].copy()
    if entry_unmapped_keys and not 'context' in new_entry:
        new_entry['context'] = {}
    for unmapped_key in entry_unmapped_keys:
        new_entry['context'][unmapped_key] = entry[unmapped_key]
    return new_entry

def convert_list(keys, tool_dests, id_map):
    block = {}
    for key in keys:
        new_id = id_map[key]
        block[new_id] = map_entry(key, tool_dests)
    return block

def get_yaml_block(thing, skip_lines=1):
    return ('\n').join(yaml.safe_dump({'tools': thing}, width=1000**2).strip('\n').split('\n')[skip_lines:]) + '\n'

gi = GalaxyInstance(eu_galaxy_url)

eu_tool_ids = [t['id'] for t in gi.tools.get_tools()]

tool_ids_dict = {get_short_id(tool_id): convert_tool_id_to_tpv_regex(tool_id) for tool_id in eu_tool_ids}

with open(eu_destinations_file) as handle:
    tool_dests = yaml.safe_load(handle)

id_map = {}
matched_keys_local = []
matched_keys_toolshed = []
data_managers = []
converters = []
interactive_tools = []
unmatched_keys = []
for key in list(tool_dests.keys()):
    unmatched = True
    if key in tool_ids_dict:
        new_id = tool_ids_dict[key]
        if '/repos/' in new_id:
            matched_keys_toolshed.append(key)
        else:
            matched_keys_local.append(key)
        unmatched = False
    elif 'data_manager' in key or 'database_builder' in key:
        data_managers.append(key)
        new_id = f'.*{key}.*'
        unmatched = False
    elif key.startswith('interactive_tool_'):
        interactive_tools.append(key)
        new_id = key
        unmatched = False
    elif key.startswith('CONVERTER_'):
        converters.append(key)
        new_id = key
        unmatched = False
    else:
        unmatched_keys.append(key)
        new_id = f'.*{key}.*'
    id_map[key] = new_id

with open('converted_tool_dests.yml', 'w') as handle:
    handle.write('tools:\n')
    # matched keys local
    handle.write('  # local tools\n')
    handle.write(get_yaml_block(convert_list(matched_keys_local, tool_dests, id_map)))
    handle.write(get_yaml_block(convert_list(converters, tool_dests, id_map)))
    handle.write(get_yaml_block(convert_list(interactive_tools, tool_dests, id_map)))
    # data managers
    handle.write('  # data managers\n')    
    handle.write(get_yaml_block(convert_list(data_managers, tool_dests, id_map)))
    # shed tools
    handle.write('  # shed tools\n')
    handle.write(get_yaml_block(convert_list(matched_keys_toolshed, tool_dests, id_map)))
    # tools that did not match to tool ids in from bioblend galaxy.tools.get_tools()
    handle.write('  # unmatched tools (could not retrieve tool ids from bioblend as an unpriveleged user)\n')
    handle.write(get_yaml_block(convert_list(unmatched_keys, tool_dests, id_map)))
