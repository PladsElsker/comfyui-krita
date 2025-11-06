# Krita integration in ComfyUI
Minimal Krita extension and ComfyUI custom nodes for integrating both together. 

## ⚠️ WIP
This project is in active development. 

## 🔨 Scope of the project
### Krita
- [x] Requires only a running and accessible ComfyUI server
- [x] Minimizes patching and hijacking of ComfyUI internals to avoid maintenance hell
- [ ] Exposes the necessary Krita operations through a websocket client
- [ ] Selects which ComfyUI client to interact with
- [ ] Dynamically updates the workflow inputs in Krita based on the opened workflow in ComfyUI
- [ ] Allows users to select a set of list of layers to composite before sending as workflow input

### ComfyUI
- [ ] Exposes the currently opened workflow in the UI
- [ ] `KritaInstance`: selects which Krita instance to interact with
- [ ] `KritaLayerSet`: composites selected Krita layers and sends them as a single image to ComfyUI
- [ ] `KritaActiveSelection`: retrieves the active selection mask
- [ ] `KritaCreateLayer`: sends the generated image back to a specified location in Krita’s layer tree

## 🎲 Why another krita plugin? 
Existing Krita–ComfyUI plugins tend to do both **too much** and **too little**.

An idiomatic plugin:
- Avoids unnecessary dependencies  
- Preserves native features of both Krita and ComfyUI  
- Respects user workflows without intrusive overrides 
