# noqa: N999
SI1 = """
{
    "id": "d2491bed-c229-4a06-a6bd-f6b237bdb534",
    "revision": 0,
    "last_node_id": 3,
    "last_link_id": 1,
    "nodes": [
        {
            "id": 2,
            "type": "KritaSaveImage-15347",
            "pos": [940, 410],
            "size": [270, 82],
            "flags": {},
            "order": 0,
            "mode": 0,
            "inputs": [
                {
                    "localized_name": "image",
                    "name": "image",
                    "type": "IMAGE",
                    "link": 1
                }
            ],
            "outputs": [],
            "properties": { "Node name for S&R": "KritaSaveImage-15347" },
            "widgets_values": [null, null]
        },
        {
            "id": 3,
            "type": "LoadImage",
            "pos": [490, 420],
            "size": [274.080078125, 314],
            "flags": {},
            "order": 1,
            "mode": 0,
            "inputs": [
                {
                    "localized_name": "image",
                    "name": "image",
                    "type": "COMBO",
                    "widget": { "name": "image" },
                    "link": null
                },
                {
                    "localized_name": "choose file to upload",
                    "name": "upload",
                    "type": "IMAGEUPLOAD",
                    "widget": { "name": "upload" },
                    "link": null
                }
            ],
            "outputs": [
                {
                    "localized_name": "IMAGE",
                    "name": "IMAGE",
                    "type": "IMAGE",
                    "links": [1]
                },
                {
                    "localized_name": "MASK",
                    "name": "MASK",
                    "type": "MASK",
                    "links": null
                }
            ],
            "properties": { "Node name for S&R": "LoadImage" },
            "widgets_values": ["UrlSend_01190_.png", "image"]
        }
    ],
    "links": [[1, 3, 0, 2, 0, "IMAGE"]],
    "groups": [],
    "config": {},
    "extra": {
        "ds": { "scale": 1, "offset": [0, 0] },
        "workflowRendererVersion": "LG"
    },
    "version": 0.4
}
"""
