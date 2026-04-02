# Signature Fault in OpenSource DevEco Studio

### Issue
> Unable to obtain user group information.
> Check the following configurations:HTTP Proxy,Network connection,GRS Cache,etc.

![Signature Fault Screen Capture](/imgs/2026-04-02/aZy5d8UqIAhrrcMY.png)![](https://segmentfault.com/img/bVdeeqW)

### Solution
1. 在 `File ->Project Structure ->Signing Config下找到签名文件存储目录
2. 删掉material文件夹。(默认路径：C:\Users\用户名\.ohos\config)

3.  选择file-\>invalidate caches，全部勾选清理缓存并重启ide。
4.  选择file-\>project structure-\>signing config重新生成签名文件。

#### Referecens
1. https://segmentfault.com/q/1010000045298737

<!--stackedit_data:
eyJoaXN0b3J5IjpbMjAyMTQxNjc5OV19
-->