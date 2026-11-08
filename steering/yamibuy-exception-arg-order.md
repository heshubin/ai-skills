---
inclusion: fileMatch
fileMatchPattern: "**/*.java"
---

# YamibuyException 两参构造的参数顺序

central-core 的 `YamibuyException(T body, String messageId)`：**第一个参数是 body，第二个才是 messageId**（javap 反编译确认：`ErrorResponse.sendException(arg2, arg1)`）。

- `new YamibuyException("提示文案", MessageCode.COMMON_BUSINESS_ERROR.getCode())` → messageId=99998，body=提示文案。Central 二期页（orderRecordController 的 `MESSAGE_ID_BUSINESS_ERROR` 分支）对 99998 原样显示 body。
- wms-cloud-service 里大量老代码写反了：`new YamibuyException(MessageCode.X.getCode(), "文案")`，实际 messageId=文案、body=错误码。改老校验时不要顺手"修正"，会改变前端看到的结果。
- 单测断言用 `e.response.messageId` / `e.response.body`，不要用 `e.message`（为 null）。

来源：Bug#10841（OP-40026，2026-11-05）手动组批类型校验。
