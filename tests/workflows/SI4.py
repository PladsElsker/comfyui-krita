SI4 = """
{
    "id": "d2491bed-c229-4a06-a6bd-f6b237bdb534",
    "revision": 0,
    "last_node_id": 6,
    "last_link_id": 4,
    "nodes": [
        {
            "id": 5,
            "type": "KritaSaveImage-15347",
            "pos": [1340, 450],
            "size": [270, 82],
            "flags": {},
            "order": 4,
            "mode": 0,
            "inputs": [
                {
                    "localized_name": "image",
                    "name": "image",
                    "type": "IMAGE",
                    "link": 3
                }
            ],
            "outputs": [],
            "properties": { "Node name for S&R": "KritaSaveImage-15347" },
            "widgets_values": ["badaboom", null]
        },
        {
            "id": 2,
            "type": "KritaSaveImage-15347",
            "pos": [990, 370],
            "size": [270, 82],
            "flags": {},
            "order": 2,
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
            "widgets_values": ["badaboom", null]
        },
        {
            "id": 4,
            "type": "KritaSaveImage-15347",
            "pos": [1220, 630],
            "size": [270, 82],
            "flags": {},
            "order": 3,
            "mode": 0,
            "inputs": [
                {
                    "localized_name": "image",
                    "name": "image",
                    "type": "IMAGE",
                    "link": 2
                }
            ],
            "outputs": [],
            "properties": { "Node name for S&R": "KritaSaveImage-15347" },
            "widgets_values": ["banner", null]
        },
        {
            "id": 6,
            "type": "KritaSaveImage-15347",
            "pos": [920, 760],
            "size": [270, 82],
            "flags": {},
            "order": 1,
            "mode": 0,
            "inputs": [
                {
                    "localized_name": "image",
                    "name": "image",
                    "type": "IMAGE",
                    "link": 4
                }
            ],
            "outputs": [],
            "properties": { "Node name for S&R": "KritaSaveImage-15347" },
            "widgets_values": ["banner", null]
        },
        {
            "id": 3,
            "type": "LoadImage",
            "pos": [490, 420],
            "size": [274.080078125, 314],
            "flags": {},
            "order": 0,
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
                    "links": [1, 2, 3, 4]
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
    "links": [
        [1, 3, 0, 2, 0, "IMAGE"],
        [2, 3, 0, 4, 0, "IMAGE"],
        [3, 3, 0, 5, 0, "IMAGE"],
        [4, 3, 0, 6, 0, "IMAGE"]
    ],
    "groups": [],
    "config": {},
    "extra": {
        "ds": { "scale": 1, "offset": [0, 0] },
        "workflowRendererVersion": "LG"
    },
    "version": 0.4
}
"""
