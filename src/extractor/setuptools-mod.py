def setup(**attrs):
    # Make sure we have any requirements needed to interpret 'attrs'.
    if not os.environ.get("dump_setup_attrs", None):
        _install_setup_requires(attrs)
    return distutils.core.setup(**attrs)