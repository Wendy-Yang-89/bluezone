# KTX Format Conversion
1. others -> .ktx
	```sh
	toktx [options] <outfile> [<infile>.{jpg,png,pam,pgm,ppm} ...]
	```
	Usage Reference: https://github.khronos.org/KTX-Software/ktxtools/toktx.html
	> **Note**: tohex 不支持**.hdr** / *.exr*格式的输入，需要预先转换成其支持的格式
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




<!--stackedit_data:
eyJoaXN0b3J5IjpbODQ0NzM1MjQ0LDExODU0MzE0NTAsLTE4Nz
AzMTU3NzQsLTE5NTgwMDk0OThdfQ==
-->