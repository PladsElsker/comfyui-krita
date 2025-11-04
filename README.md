# ComfyUI integration in Krita

## Why another krita plugin? 
All the existing plugins that attempt to integrate ComfyUI in Krita do both too much and too little.  

An idiomatic plugin does not require dependencies that can be made optional. For users that are familiar with either ComfyUI or Krita, it shouldn't feel like you have to give up on anything to use the plugin. 

## Scope of the project
- The extension features are clear and unambiguous: 
  - [ ] ComfyUI's UI must be integrated in a Krita docker
  - [ ] The only required dependency is to have a ComfyUI server open and accessible somewhere
  - [ ] As little patching and highjacking as realistically possible on top of ComfyUI
  - [ ] ComfyUI live previews work when running a workow from Krita
  - Custom nodes are used for interacting with Krita:
    - [ ] `KritaLayerSet` node: select which layers to composite in Krita before sending as an image to ComfyUI
    - [ ] `KritaActiveSelection` node: get the active selection mask
    - [ ] `KritaCreateLayer` node: send the image back to Krita to a given location in the layer tree
    
