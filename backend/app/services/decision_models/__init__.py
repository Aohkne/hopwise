"""Client gọi 2 model (Jev, LLM) — cùng giao diện `decide(state, questions)`."""

import httpx

# Timeout dùng CHUNG cho cả 2 client, để 2 model chịu cùng một luật:
# - không giới hạn thời gian chờ phản hồi của 1 lần gọi — giới hạn thật là 5 phút
#   cho cả lượt tìm của mỗi model (BENCH_TIMEOUT_SECONDS, asyncio.wait_for trong
#   benchmark.py), không cắt từng lần gọi.
# - giữ timeout kết nối ngắn: không kết nối được thì báo lỗi ngay
#   thay vì chờ hết 5 phút.
CALL_TIMEOUT = httpx.Timeout(None, connect=5)
