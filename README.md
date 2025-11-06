# ComfyUI integration in Krita
Minimal Krita extension and ComfyUI custom nodes for integrating both together. 

## ⚠️ WIP
This extension is in active development. 

## 🔨 Scope of the project
### Krita
- [ ] Integrate ComfyUI's UI in a Krita docker
- [x] Implement as little patching and highjacking as realistically possible on top of ComfyUI
- [ ] Allow ComfyUI live previews to work when running a workflow from Krita
- [ ] Implement dynamic workflow inputs that are parsed from the currently selected ComfyUI workflow
- [ ] Implement a custom "layer-set selector" component to select the set of layers to composite before sending to ComfyUI

### ComfyUI
Custom nodes are used for interacting with Krita:
- [ ] `KritaLayerSet` node: select which layers to composite in Krita before sending as an image to ComfyUI
- [ ] `KritaActiveSelection` node: get the active selection mask
- [ ] `KritaCreateLayer` node: send the image back to Krita to a given location in the layer tree

## 🎲 Why another krita plugin? 
All the existing plugins that attempt to integrate ComfyUI in Krita do both **too much** and **too little**.  

An idiomatic plugin:
- Does not require dependencies that can be made optional
- Does not take away features that were granted in either Krita or ComfyUI
