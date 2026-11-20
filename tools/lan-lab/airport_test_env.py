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
