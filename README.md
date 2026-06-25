# Mini Python IDE — 第 1 步:跑通执行链路

浏览器写 Python 代码 → FastAPI 后端 → Judge0 执行 → 显示结果。

## 运行

```bash
# 1) 建虚拟环境(可选但推荐)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2) 装依赖
pip install -r requirements.txt

# 3) 启动
uvicorn main:app --reload
```

然后浏览器打开 http://localhost:8000/ ,点「运行」。
看到 `hello, world` 和 `1~10 的和 = 55` 就说明整条链路通了。

## 配置(都有默认值,先用默认跑)

通过环境变量调整,例如:

```bash
# macOS / Linux
export JUDGE0_URL=https://ce.judge0.com
export PYTHON_LANGUAGE_ID=71
uvicorn main:app --reload
```

| 变量 | 作用 | 默认 |
|---|---|---|
| `JUDGE0_URL` | Judge0 地址 | `https://ce.judge0.com` |
| `PYTHON_LANGUAGE_ID` | Python 的语言 ID | `71` |
| `JUDGE0_AUTH_HEADER_NAME` | 鉴权头名字(需要时) | 空 |
| `JUDGE0_AUTH_HEADER_VALUE` | 鉴权头的值 | 空 |

## 常见问题

- **报 401 / 429**:公共实例 `ce.judge0.com` 额度有限、可能要鉴权。两条路:
  - 注册一个有 key 的托管服务(如 RapidAPI 上的 Judge0 / Sulu),把 key 填进
    `JUDGE0_AUTH_HEADER_NAME` + `JUDGE0_AUTH_HEADER_VALUE`。
    (RapidAPI 还需要额外的 `X-RapidAPI-Host` 头,可在 `judge0_headers()` 里手动加。)
  - 或自托管:`git clone judge0/judge0` 后 `docker compose up`,把 `JUDGE0_URL`
    改成你的地址(自托管一般用 `X-Auth-Token` 头鉴权)。
- **输出乱码 / 缺失**:本最小版用了 `base64_encoded=false`,极少数含不可打印字符的
  输出可能出问题。需要严谨处理时改用 base64 编码收发。
- **语言 ID 不对**:不同 Judge0 实例的 Python ID 可能不是 71。访问
  `<JUDGE0_URL>/languages` 查一下 Python 3 对应的 id,填到 `PYTHON_LANGUAGE_ID`。

## 这一步的边界

后端**不自己跑代码**,只转发给 Judge0 的沙箱。所以这一步天然是安全的——
你的服务器不会执行用户的任意 Python。后面接小程序时,这套后端逻辑基本不用改。
