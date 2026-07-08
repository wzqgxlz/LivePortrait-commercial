## The directory structure of `pretrained_weights`

This commercial-safe build uses MediaPipe for face detection and must not include
legacy third-party face-detection model weights.

```text
pretrained_weights
|-- liveportrait
|   |-- base_models
|   |   |-- appearance_feature_extractor.pth
|   |   |-- motion_extractor.pth
|   |   |-- spade_generator.pth
|   |   `-- warping_module.pth
|   |-- landmark.onnx
|   `-- retargeting_models
|       `-- stitching_retargeting_module.pth
`-- liveportrait_animals
    |-- base_models
    |   |-- appearance_feature_extractor.pth
    |   |-- motion_extractor.pth
    |   |-- spade_generator.pth
    |   `-- warping_module.pth
    |-- retargeting_models
    |   `-- stitching_retargeting_module.pth
    `-- xpose.pth
```
