# Signature Fault in OpenSource DevEco Studio

### Issue
> Unable to obtain user group information.
> Check the following configurations:HTTP Proxy,Network connection,GRS Cache,etc.

![Signature Fault Screen Capture](/imgs/2026-04-02/aZy5d8UqIAhrrcMY.png)![](https://segmentfault.com/img/bVdeeqW)

### Solution
1. Locate the signature file storage directory under `File -> Project Structure -> Signing Config`.
2. If the above directory does not exist, find the default path: `C:\Users\${UserName}\.ohos\config`
3. Delete the `material` directory.
4. Select `File -> Invalidate Caches`, check all options, and click `Invalidate and Restart` to restart the IDE.
5. Regenerate the signing file in the `File -> Project Structure -> Signing Config` interface.

#### Referecens
1. https://segmentfault.com/q/1010000045298737

<!--stackedit_data:
eyJoaXN0b3J5IjpbNjk5NjA3Nzc4XX0=
-->