---
inclusion: fileMatch
fileMatchPattern: '**/*.java,**/*.groovy,**/pom.xml,**/*.sql'
---
# Java 开发环境配置

## Maven 配置

- **Maven 路径**: `D:\maven\apache-maven-3.9.11`
- **可执行文件**: `D:\maven\apache-maven-3.9.11\bin\mvn.cmd`
- **Settings 文件**: `D:\maven\apache-maven-3.9.11\conf\settings.xml`
- **本地仓库**: `D:\maven\repository`
- **私服地址**: `https://nexus.yamibuy.net/repository/maven-public/`

### Maven 命令模板

```powershell
# 编译
D:\maven\apache-maven-3.9.11\bin\mvn.cmd compile -s "D:\maven\apache-maven-3.9.11\conf\settings.xml"

# 运行测试
D:\maven\apache-maven-3.9.11\bin\mvn.cmd test -s "D:\maven\apache-maven-3.9.11\conf\settings.xml" -Dtest="测试类名"

# 打包（跳过测试）
D:\maven\apache-maven-3.9.11\bin\mvn.cmd package -s "D:\maven\apache-maven-3.9.11\conf\settings.xml" -DskipTests
```

> 注意：PowerShell 中 `-D` 参数需要用引号包裹，避免被解析为 PowerShell 参数。例如 `"-Dtest=XxxTest"`

## Java 环境

- **JDK 路径**: `C:\Program Files\Java\jdk-17`
- **Java 版本**: JDK 17

## wms-cloud-service 服务启动配置

### GQC 环境 VM Options

```
-Dapollo.configService=https://gqc-apollo-configservice.yamibuy.tech
-Dspring.datasource.url=jdbc:mysql://eks-gqc-8-cluster.cluster-c5ywutgewymm.us-west-2.rds.amazonaws.com:3306/Yamibuy_Master?characterEncoding=UTF-8&allowMultiQueries=true&useSSL=false&&serverTimezone=UTC
-Dyamibuy.queue.rabbitmq.host=35.85.43.120
-Dspring.redis.host=gqc-serverless-redis.yamibuy.tech
-Dserver.servlet.context-path=/wms
-Dfeign.hub.name=hub
-Dfeign.hub.url=https://gqc-centralapi.yamibuy.tech/hub
-Dspring.datasource.username=${GQC_DB_USER}
-Dspring.datasource.password=${GQC_DB_PASSWORD}
-Dspring.redis.timeout=30000
-Dredisson.timeout=30000
-Dspring.redis.core.lock.host=gqc-lock-redis.yamibuy.tech
```

> 数据库账号密码已脱敏：`${GQC_DB_USER}` / `${GQC_DB_PASSWORD}` 的真值通过 account-password-query skill 获取，填入本地 IDE 启动配置，不要写回本文件。

### 环境说明

| 环境 | Apollo ConfigService | 数据库 | Redis |
|------|---------------------|--------|-------|
| GQC  | gqc-apollo-configservice.yamibuy.tech | eks-gqc-8-cluster...rds.amazonaws.com | gqc-serverless-redis.yamibuy.tech |

## 项目结构

### wms-cloud-service（多模块 Maven 项目）

```
wms-cloud-service/
├── pom.xml                    # 父 POM
├── wms-cloud-api/             # API 模块（实体类、DTO、枚举）
├── wms-cloud-service/         # Service 模块（业务逻辑、DAO、MyBatis）
├── wms-cloud-rest/            # REST 模块（Controller 层）
└── wms-cloud-job/             # Job 模块（定时任务）
```

### 编译顺序

编译 wms-cloud-service 模块前需要先编译 wms-cloud-api（依赖关系）：
```powershell
# 编译3个核心模块
D:\maven\apache-maven-3.9.11\bin\mvn.cmd compile -pl wms-cloud-api,wms-cloud-service,wms-cloud-rest -s "D:\maven\apache-maven-3.9.11\conf\settings.xml"
```

单独运行 wms-cloud-service 的测试前，需要先 install 父 POM 和 wms-cloud-api：
```powershell
# 第一次运行测试前需要执行（后续不需要重复）
D:\maven\apache-maven-3.9.11\bin\mvn.cmd install -N -s "D:\maven\apache-maven-3.9.11\conf\settings.xml" "-DskipTests"
D:\maven\apache-maven-3.9.11\bin\mvn.cmd install -pl wms-cloud-api -s "D:\maven\apache-maven-3.9.11\conf\settings.xml" "-DskipTests"
```

### 单元测试框架

- **测试框架**: Spock（Groovy）
- **测试文件位置**: `wms-cloud-service/src/test/java/`
- **测试文件后缀**: `.groovy`
- **运行单个测试**:
```powershell
D:\maven\apache-maven-3.9.11\bin\mvn.cmd test -pl wms-cloud-service -s "D:\maven\apache-maven-3.9.11\conf\settings.xml" "-Dtest=com.yamibuy.wms.cloud.service.lot.LotServiceTest"
```
