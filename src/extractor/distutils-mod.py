
    def dump():
        def jsonify(obj):
            if isinstance(obj, str):
                return obj
            if sys.version_info < (3, 0) and isinstance(obj, unicode):
                return str(obj)
            if isinstance(obj, bytes):
                return obj.decode()
            if isinstance(obj, dict):
                return {jsonify(key): jsonify(val) for key, val in obj.items()}
            try:
                # convert to list if possible
                return [jsonify(elem) for elem in obj]
            except:
                pass
            # fallback to string repr. of obj
            return str(obj)

        keys = (
            'install_requires',
            'setup_requires',
            'extras_require',
            'tests_require',
            'python_requires'
        )
        data = {}
        for key in keys:
            val = getattr(dist, key, None)
            if not val:
                continue
            data[key] = jsonify(val)
        return data
    if os.environ.get("dump_setup_attrs", None):
        import json
        try:
            data = dump()
        except:
            import traceback
            data = dict(traceback=traceback.format_exc())
        out = os.environ.get("out_file")
        with open(out, 'w') as f:
            json.dump(data, f, indent=2)
        exit()
