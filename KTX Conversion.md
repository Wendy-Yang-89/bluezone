# KTX Format Conversion
1. others -> .ktx
	```sh
	toktx [options] <outfile> [<infile>.{jpg,png,pam,pgm,ppm} ...]
	```
	Usage Reference: https://github.khronos.org/KTX-Software/ktxtools/toktx.html
3. .kxt -> .kxt2
	```sh
	ktx2ktx2 [options] [<infile> ...]
	```
	Usage Reference: https://github.khronos.org/KTX-Software/ktxtools/ktx2ktx2.html

#### Pratice: Generate environment map for unity and AGP
##### Unity
- Unity doest not support .ktx format
- Install **KTX for Unity** in **Package Manager** will support .ktx2 format and .basis format

###### 

<!--stackedit_data:
eyJoaXN0b3J5IjpbLTk3MzQ3MDY4OF19
-->