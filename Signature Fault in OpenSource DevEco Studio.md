# Signature Fault in OpenSource DevEco Studio

### Issue
> Unable to obtain user group information.
> Check the following configurations:HTTP Proxy,Network connection,GRS Cache,etc.

![Signature Fault Screen Capture](/imgs/2026-04-02/aZy5d8UqIAhrrcMY.png)![](https://segmentfault.com/img/bVdeeqW)

### Solution
1.  在 `File ->Project Structure ->Signing Config` 下找到签名文件存储目录
2.  若上述目录不存在则找到默认路径: C:\Users\${UserName}\.ohos\config
3.  删掉material
4.  选择 `File -> Invalidate Caches`，全部勾选后点击 `Invalidate and Restart` 重启IDE
5.  在 `File ->Project Structure ->Signing Config` 界面重新生成签名文件

#### Referecens
1. https://segmentfault.com/q/1010000045298737

<!--stackedit_data:
eyJoaXN0b3J5IjpbMTg5NjY4NjgxNF19
-->