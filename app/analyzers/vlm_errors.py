class VLMError(Exception):
    pass

class VLMTimeout(VLMError):
    pass

class VLMInvalidOutput(VLMError):
    pass