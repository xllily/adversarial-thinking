def get_resource(request, store):
    resource = store.load(request.path_params["resource_id"])
    if resource is None:
        return {"status": 404}
    return {"status": 200, "body": resource.body}
