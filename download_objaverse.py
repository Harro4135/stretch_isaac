import objaverse


annotations = objaverse.load_annotations()


cc_by_uids = [uid for uid, annotation in annotations.items() if "keyboard" in annotation["name"].lower()]
annotation = [annotation for uid, annotation in annotations.items() if "keyboard" in annotation["name"].lower()]

objects = objaverse.load_objects(
    uids=cc_by_uids[:20],
    download_processes=4,
)

for id in objects:
    print(id, objects[id])
