
def remove_prefix(text:str, prefix:str) -> str: # python < 3.9 compatibility
    if text.startswith(prefix):
        if len(prefix) > len(text): 
            return text
        return text[len(prefix):]
    return text

def remove_suffix(text:str, suffix:str) -> str: # python < 3.9 compatibility
    if text.endswith(suffix):
        if len(suffix) == 0:
            return text
        return text[:-len(suffix)]
    return text
