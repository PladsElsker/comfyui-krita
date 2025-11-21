# noqa: N999
SI5R = """
{
    "id": "d2491bed-c229-4a06-a6bd-f6b237bdb534",
    "revision": 0,
    "last_node_id": 226,
    "last_link_id": 32,
    "nodes": [
        {
            "id": 222,
            "type": "KritaSaveImage-15347",
            "pos": [920, 430],
            "size": [270, 82],
            "flags": {},
            "order": 3,
            "mode": 0,
            "inputs": [
                {
                    "localized_name": "image",
                    "name": "image",
                    "type": "IMAGE",
                    "link": 26
                }
            ],
            "outputs": [],
            "properties": { "Node name for S&R": "KritaSaveImage-15347" },
            "widgets_values": ["banner", null]
        },
        {
            "id": 224,
            "type": "fc52c966-3743-4d93-a7b6-3e37290eaf56",
            "pos": [1030, 650],
            "size": [140, 26],
            "flags": {},
            "order": 4,
            "mode": 0,
            "inputs": [{ "name": "image", "type": "IMAGE", "link": 27 }],
            "outputs": [],
            "properties": { "proxyWidgets": [] },
            "widgets_values": []
        },
        {
            "id": 226,
            "type": "e4a57186-5d42-427e-9c38-c42b6d5fc542",
            "pos": [893.4256502004165, 768.9925934872915],
            "size": [140, 26],
            "flags": {},
            "order": 2,
            "mode": 0,
            "inputs": [{ "name": "image", "type": "IMAGE", "link": 32 }],
            "outputs": [],
            "properties": { "proxyWidgets": [] },
            "widgets_values": []
        },
        {
            "id": 225,
            "type": "7a1ac581-94e0-4e82-8306-d921b667cb86",
            "pos": [1060.6536270962497, 746.0730230497915],
            "size": [140, 86],
            "flags": {},
            "order": 1,
            "mode": 0,
            "inputs": [
                { "name": "image", "type": "IMAGE", "link": 28 },
                { "name": "image_1", "type": "IMAGE", "link": 30 },
                { "name": "image_2", "type": "IMAGE", "link": 29 },
                { "name": "image_3", "type": "IMAGE", "link": 31 }
            ],
            "outputs": [],
            "properties": { "proxyWidgets": [] },
            "widgets_values": []
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
                    "links": [26, 27, 28, 29, 30, 31, 32]
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
        [26, 3, 0, 222, 0, "IMAGE"],
        [27, 3, 0, 224, 0, "IMAGE"],
        [28, 3, 0, 225, 0, "IMAGE"],
        [29, 3, 0, 225, 2, "IMAGE"],
        [30, 3, 0, 225, 1, "IMAGE"],
        [31, 3, 0, 225, 3, "IMAGE"],
        [32, 3, 0, 226, 0, "IMAGE"]
    ],
    "groups": [],
    "definitions": {
        "subgraphs": [
            {
                "id": "fc52c966-3743-4d93-a7b6-3e37290eaf56",
                "version": 1,
                "state": {
                    "lastGroupId": 0,
                    "lastNodeId": 223,
                    "lastLinkId": 27,
                    "lastRerouteId": 0
                },
                "revision": 0,
                "config": {},
                "name": "New Subgraph",
                "inputNode": {
                    "id": -10,
                    "bounding": [988.4604954504164, 677.3722008831248, 120, 60]
                },
                "outputNode": {
                    "id": -20,
                    "bounding": [1498.4604954504164, 677.3722008831248, 120, 40]
                },
                "inputs": [
                    {
                        "id": "56ea97ac-8ac3-4e88-9dbb-d52c81fd867f",
                        "name": "image",
                        "type": "IMAGE",
                        "linkIds": [27],
                        "pos": [1088.4604954504164, 697.3722008831248]
                    }
                ],
                "outputs": [],
                "widgets": [],
                "nodes": [
                    {
                        "id": 223,
                        "type": "KritaSaveImage-15347",
                        "pos": [1168.4604954504164, 671.3722008831248],
                        "size": [270, 82],
                        "flags": {},
                        "order": 0,
                        "mode": 0,
                        "inputs": [
                            {
                                "localized_name": "image",
                                "name": "image",
                                "type": "IMAGE",
                                "link": 27
                            }
                        ],
                        "outputs": [],
                        "properties": {
                            "Node name for S&R": "KritaSaveImage-15347"
                        },
                        "widgets_values": ["banner", null]
                    }
                ],
                "groups": [],
                "links": [
                    {
                        "id": 27,
                        "origin_id": -10,
                        "origin_slot": 0,
                        "target_id": 223,
                        "target_slot": 0,
                        "type": "IMAGE"
                    }
                ],
                "extra": { "workflowRendererVersion": "LG" }
            },
            {
                "id": "7a1ac581-94e0-4e82-8306-d921b667cb86",
                "version": 1,
                "state": {
                    "lastGroupId": 0,
                    "lastNodeId": 227,
                    "lastLinkId": 31,
                    "lastRerouteId": 0
                },
                "revision": 0,
                "config": {},
                "name": "New Subgraph",
                "inputNode": {
                    "id": -10,
                    "bounding": [988.4604954504164, 677.3722008831248, 120, 120]
                },
                "outputNode": {
                    "id": -20,
                    "bounding": [1498.4604954504164, 677.3722008831248, 120, 40]
                },
                "inputs": [
                    {
                        "id": "56ea97ac-8ac3-4e88-9dbb-d52c81fd867f",
                        "name": "image",
                        "type": "IMAGE",
                        "linkIds": [29],
                        "pos": [1088.4604954504164, 697.3722008831248]
                    },
                    {
                        "id": "bed9a116-2884-4d0b-a726-6bdd099897a5",
                        "name": "image_1",
                        "type": "IMAGE",
                        "linkIds": [28],
                        "pos": [1088.4604954504164, 717.3722008831248]
                    },
                    {
                        "id": "74cd8474-8bf0-4618-ae5c-e264cd6e896a",
                        "name": "image_2",
                        "type": "IMAGE",
                        "linkIds": [30],
                        "pos": [1088.4604954504164, 737.3722008831248]
                    },
                    {
                        "id": "dcb44131-e648-497f-a34f-52c463b39e44",
                        "name": "image_3",
                        "type": "IMAGE",
                        "linkIds": [31],
                        "pos": [1088.4604954504164, 757.3722008831248]
                    }
                ],
                "outputs": [],
                "widgets": [],
                "nodes": [
                    {
                        "id": 226,
                        "type": "KritaSaveImage-15347",
                        "pos": [1190, 960],
                        "size": [270, 82],
                        "flags": {},
                        "order": 3,
                        "mode": 4,
                        "inputs": [
                            {
                                "localized_name": "image",
                                "name": "image",
                                "type": "IMAGE",
                                "link": 30
                            }
                        ],
                        "outputs": [],
                        "properties": {
                            "Node name for S&R": "KritaSaveImage-15347"
                        },
                        "widgets_values": ["banner", null]
                    },
                    {
                        "id": 224,
                        "type": "KritaSaveImage-15347",
                        "pos": [1299.3768156420897, 857.3166408351104],
                        "size": [270, 82],
                        "flags": {},
                        "order": 1,
                        "mode": 2,
                        "inputs": [
                            {
                                "localized_name": "image",
                                "name": "image",
                                "type": "IMAGE",
                                "link": 28
                            }
                        ],
                        "outputs": [],
                        "properties": {
                            "Node name for S&R": "KritaSaveImage-15347"
                        },
                        "widgets_values": ["banner", null]
                    },
                    {
                        "id": 227,
                        "type": "KritaSaveImage-15347",
                        "pos": [1290, 540],
                        "size": [270, 82],
                        "flags": {},
                        "order": 0,
                        "mode": 0,
                        "inputs": [
                            {
                                "localized_name": "image",
                                "name": "image",
                                "type": "IMAGE",
                                "link": 31
                            }
                        ],
                        "outputs": [],
                        "properties": {
                            "Node name for S&R": "KritaSaveImage-15347"
                        },
                        "widgets_values": ["banner", null]
                    },
                    {
                        "id": 225,
                        "type": "9f8db2a0-1aed-4e46-81d0-76ea46f1b415",
                        "pos": [1230, 700],
                        "size": [140, 26],
                        "flags": {},
                        "order": 2,
                        "mode": 0,
                        "inputs": [
                            {
                                "localized_name": "image",
                                "name": "image",
                                "type": "IMAGE",
                                "link": 29
                            }
                        ],
                        "outputs": [],
                        "properties": { "proxyWidgets": [] },
                        "widgets_values": []
                    }
                ],
                "groups": [],
                "links": [
                    {
                        "id": 28,
                        "origin_id": -10,
                        "origin_slot": 1,
                        "target_id": 224,
                        "target_slot": 0,
                        "type": "IMAGE"
                    },
                    {
                        "id": 29,
                        "origin_id": -10,
                        "origin_slot": 0,
                        "target_id": 225,
                        "target_slot": 0,
                        "type": "IMAGE"
                    },
                    {
                        "id": 30,
                        "origin_id": -10,
                        "origin_slot": 2,
                        "target_id": 226,
                        "target_slot": 0,
                        "type": "IMAGE"
                    },
                    {
                        "id": 31,
                        "origin_id": -10,
                        "origin_slot": 3,
                        "target_id": 227,
                        "target_slot": 0,
                        "type": "IMAGE"
                    }
                ],
                "extra": { "workflowRendererVersion": "LG" }
            },
            {
                "id": "e4a57186-5d42-427e-9c38-c42b6d5fc542",
                "version": 1,
                "state": {
                    "lastGroupId": 0,
                    "lastNodeId": 223,
                    "lastLinkId": 27,
                    "lastRerouteId": 0
                },
                "revision": 0,
                "config": {},
                "name": "New Subgraph",
                "inputNode": {
                    "id": -10,
                    "bounding": [988.4604954504164, 677.3722008831248, 120, 60]
                },
                "outputNode": {
                    "id": -20,
                    "bounding": [1498.4604954504164, 677.3722008831248, 120, 40]
                },
                "inputs": [
                    {
                        "id": "56ea97ac-8ac3-4e88-9dbb-d52c81fd867f",
                        "name": "image",
                        "type": "IMAGE",
                        "linkIds": [27],
                        "pos": [1088.4604954504164, 697.3722008831248]
                    }
                ],
                "outputs": [],
                "widgets": [],
                "nodes": [
                    {
                        "id": 223,
                        "type": "KritaSaveImage-15347",
                        "pos": [1168.4604954504164, 671.3722008831248],
                        "size": [270, 82],
                        "flags": {},
                        "order": 0,
                        "mode": 0,
                        "inputs": [
                            {
                                "localized_name": "image",
                                "name": "image",
                                "type": "IMAGE",
                                "link": 27
                            }
                        ],
                        "outputs": [],
                        "properties": {
                            "Node name for S&R": "KritaSaveImage-15347"
                        },
                        "widgets_values": ["banner", null]
                    }
                ],
                "groups": [],
                "links": [
                    {
                        "id": 27,
                        "origin_id": -10,
                        "origin_slot": 0,
                        "target_id": 223,
                        "target_slot": 0,
                        "type": "IMAGE"
                    }
                ],
                "extra": { "workflowRendererVersion": "LG" }
            },
            {
                "id": "9f8db2a0-1aed-4e46-81d0-76ea46f1b415",
                "version": 1,
                "state": {
                    "lastGroupId": 0,
                    "lastNodeId": 224,
                    "lastLinkId": 28,
                    "lastRerouteId": 0
                },
                "revision": 0,
                "config": {},
                "name": "New Subgraph",
                "inputNode": {
                    "id": -10,
                    "bounding": [988.4604954504164, 667.3722008831248, 120, 60]
                },
                "outputNode": {
                    "id": -20,
                    "bounding": [1498.4604954504164, 677.3722008831248, 120, 40]
                },
                "inputs": [
                    {
                        "id": "9e1da9ce-1d2d-4bae-894e-721d5e904dfe",
                        "name": "image",
                        "type": "IMAGE",
                        "linkIds": [27],
                        "localized_name": "image",
                        "pos": [1088.4604954504164, 687.3722008831248]
                    }
                ],
                "outputs": [],
                "widgets": [],
                "nodes": [
                    {
                        "id": 223,
                        "type": "KritaSaveImage-15347",
                        "pos": [1168.4604954504164, 671.3722008831248],
                        "size": [270, 82],
                        "flags": {},
                        "order": 0,
                        "mode": 0,
                        "inputs": [
                            {
                                "localized_name": "image",
                                "name": "image",
                                "type": "IMAGE",
                                "link": 27
                            }
                        ],
                        "outputs": [],
                        "properties": {
                            "Node name for S&R": "KritaSaveImage-15347"
                        },
                        "widgets_values": ["banner", null]
                    }
                ],
                "groups": [],
                "links": [
                    {
                        "id": 27,
                        "origin_id": -10,
                        "origin_slot": 0,
                        "target_id": 223,
                        "target_slot": 0,
                        "type": "IMAGE"
                    }
                ],
                "extra": { "workflowRendererVersion": "LG" }
            }
        ]
    },
    "config": {},
    "extra": {
        "workflowRendererVersion": "LG",
        "ds": {
            "scale": 1.1780325496774484,
            "offset": [48.8233566745836, -117.05814548729145]
        }
    },
    "version": 0.4
}
"""
