accessory_registry = {}


def register(type_: str, icon: str):
    """
    Class decorator to register an accessory
    :param cls: the class to register.
    :param type_: type to match in the Controls file
    :param icon: icon to match in the Controls file
    """
    def register_(cls: type):
        if (type_, icon) in accessory_registry:
            raise ValueError(f"Duplicate accessory for type={type_!r}, icon={icon!r}")
        accessory_registry[(type_, icon)] = cls
        return cls

    return register_
