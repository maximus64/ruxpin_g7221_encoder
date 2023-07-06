# G.722.1 Encoder for Teddy Ruxpin and Cloudpets

## Introduction
The G.722.1 encoder provided here is specifically designed for Teddy Ruxpin and Cloudpets, both of which utilize a similar G.722.1 codec. This encoder addresses certain peculiarities found in these systems. It is based on the ITU-T G.722.1 Release 2.1 (2008-06) reference code, with additional patches applied to ensure compatibility with the codec used in Cloudpets and Teddy Ruxpin.

## Encoding Audio
To encode audio using this encoder, follow the steps below:

1. Convert the input audio file to PCM format:
```
$ ffmpeg -i input.wav -f s16le -ar 16000 -ac 1 -acodec pcm_s16le pcm.raw
```
2. Execute the encoder:
```
$ ./encode 0 pcm.raw out.bin 16000 7000
```

## Acknowledgements
Special thanks to the following contributors for their support and involvement:
- @BuyitFixit
- @ladyada
- @zenofex
- [cloudpets-web-bluetooth](https://github.com/pdjstone/cloudpets-web-bluetooth)

Please note that this encoder is provided as-is and may require additional configuration or modifications based on your specific implementation.