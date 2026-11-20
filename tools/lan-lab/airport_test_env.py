"""LAN defaults for the isolated airport test app, not for ordinary exports."""
def with_lan_defaults(text):
    keys={line.partition('=')[0].strip() for line in text.splitlines()
          if '=' in line and not line.lstrip().startswith('#')}
    missing=[f'{key}={value}' for key,value in (('DM_LAN','1'),('DM_LDN_TRACE','1')) if key not in keys]
    if not missing:return text
    return text+('' if not text or text.endswith('\n') else '\n')+'\n'.join(missing)+'\n'

def release_environment(text):
    """Keep the proven compatibility settings without default diagnostic tracing."""
    lines=[line for line in with_lan_defaults(text).splitlines()
           if line.partition('=')[0].strip()!='DM_LDN_TRACE']
    return '\n'.join(lines)+'\n'

def export_bundle_id(release, upgrade_test_app=False):
    """A release upgrades the original app unless the test upgrade is explicit."""
    if upgrade_test_app and not release:
        raise ValueError('Upgrading the test app as a release requires release mode')
    return 'org.spplechos.shell' if release and not upgrade_test_app else 'org.spplechos.acnh.airporttest'
