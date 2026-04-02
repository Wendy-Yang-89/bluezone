# Signature Fault in OpenSource DevEco Studio


![Signature Fault Screen Capture](/imgs/2026-04-02/aZy5d8UqIAhrrcMY.png)![](https://segmentfault.com/img/bVdeeqW)

### 解决方法
1. 在 `file ->project structure ->signing config下找到签名文件存储目录，删掉material文件夹。(默认路径：C:\Users\用户名\.ohos\config)

2.  选择file-\>invalidate caches，全部勾选清理缓存并重启ide。
3.  选择file-\>project structure-\>signing config重新生成签名文件。

#### Referecens
1. https://segmentfault.com/q/1010000045298737

<!--stackedit_data:
eyJoaXN0b3J5IjpbNDQzNTUyOTg2XX0=
-->