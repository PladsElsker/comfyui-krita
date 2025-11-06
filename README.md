# ComfyUI integration in Krita
Minimal Krita extension and ComfyUI custom nodes for integrating both together. 

## ⚠️ WIP
This extension is in active development. 

## 🔨 Scope of the project
### Krita
- [x] Requires only a running and accessible ComfyUI server
- [ ] Integrate ComfyUI's UI in a Krita docker
- [x] Minimize patching and highjacking of ComfyUI internals
- [ ] Enable live ComfyUI previews when running a workflow from Krita
- [ ] Parse dynamic workflow inputs from the selected ComfyUI workflow
- [ ] Add a custom **Layer Set Selector** component to choose which layers to composite before sending to ComfyUI

### ComfyUI
Custom nodes for Krita interaction:
- [ ] `KritaLayerSet`: composites selected layers in Krita before sending them as an image to ComfyUI
- [ ] `KritaActiveSelection`: retrieves the active selection mask
- [ ] `KritaCreateLayer`: sends the generated image back to a specified location in Krita’s layer tree

## 🎲 Why another krita plugin? 
Existing Krita–ComfyUI plugins tend to do both **too much** and **too little**.

An idiomatic plugin:
- Avoids unnecessary dependencies  
- Preserves native features of both Krita and ComfyUI  
- Respects user workflows without intrusive overrides 
