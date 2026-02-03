# KTX Format Conversion

### KTX-Softwarer commands
1. others -> .ktx
	```sh
	toktx [options] <outfile> [<infile>.{jpg,png,pam,pgm,ppm} ...]
	```
	Usage Reference: https://github.khronos.org/KTX-Software/ktxtools/toktx.html
	> **Note**: toktx 不支持.hdr/.exr格式的输入，需要预先转换成其支持的格式
	> - ImageMagick: https://imagemagick.org/script/download.php
	> - 
	
3. .kxt -> .kxt2
	```sh
	ktx2ktx2 [options] [<infile> ...]
	```
	Usage Reference: https://github.khronos.org/KTX-Software/ktxtools/ktx2ktx2.html

#### Pratice: Generate environment map for AGP and Unity

##### AGP
- AGP only support *.kxt* format input when using **Cubemap** type environment

###### *.ktx* Generation
```sh
# 完整命令：生成 mipmap + BC6H HDR 压缩 + 输出 KTX1 
toktx --genmipmap --bc6h hdr_texture.ktx input.hdr
```


##### Unity
- Unity doest not support *.ktx* format
- Install **KTX for Unity** in **Package Manager** will support *.ktx2* format and .basis format
- Unity also supports 6-Sided Cubemap input for skybox material

###### *.ktx2* Generation
```sh
# 完整命令：生成 mipmap + BC6H HDR 压缩 + 输出 KTX1 
toktx --genmipmap --bc6h hdr_texture.ktx input.hdr
```
###### 6-Sided Cubemap Generation

### Tool: cmftStudio
-   下载地址：[https://github.com/dariomanesku/cmftStudio/releases](https://github.com/dariomanesku/cmftStudio/releases)
-   操作步骤：
    -   导入 HDR 全景图 → 选择输出类型为 `KTX`/`KTX2`。
    -   配置参数（分辨率、mipmap、压缩格式 BC6H）→ 点击 `Run` 导出。
    -   优势：自动处理坐标转换，无需担心天空盒颠倒问题。

### TextureLab

1.  下载地址：[https://github.com/njbrown/texturelab](https://github.com/njbrown/texturelab)
2.  操作步骤：
    -   拖入 HDR 文件 → 添加 `KTX Exporter` 节点。
    -   配置压缩格式（BC6H 用于 HDR）→ 导出 KTX 文件。
    -   优势：支持可视化编辑（如亮度调整、模糊），适合处理后再导出。

# Q&A
1. **Q**: toktx cannot recognize *.ppm* format input 
	   
	   toktx: failed to create image from belfast_sunset_puresky_4k.ppm(0,0). No image plugin recognized the format of "belfast_sunset_puresky_4k.ppm". 
		Is it a file format that we don't know about?
	
	**A**: Netpbm 格式（包含 PPM）有两种变体：

		1.  **P6 格式（二进制）**：`toktx` 唯一支持的 PPM 格式，文件体积小，数据以二进制存储，无冗余注释。
		2.  **P3 格式（ASCII）**：人类可读的文本格式，`toktx` 不支持，会直接报「无法识别格式」错误。

另外，`toktx` 仅支持 **3 通道（RGB）** 的 PPM，不支持 4 通道（RGBA），若生成的 PPM 包含 Alpha 通道，也会识别失败。
<!--stackedit_data:
eyJoaXN0b3J5IjpbNDU0MDU5NTI0LDE3MjkzNjIyNzQsMTk1MD
Q0MTE2MCwxMTg1NDMxNDUwLC0xODcwMzE1Nzc0LC0xOTU4MDA5
NDk4XX0=
-->