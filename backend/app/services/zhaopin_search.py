from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from app.services.browser_bridge import BrowserBridge, BrowserBridgeError


@dataclass
class ZhaopinSearchJob:
    title: str
    company_name: str
    city: str
    salary_text: str
    salary_min: int | None
    salary_max: int | None
    degree_required: str
    experience_required: str
    company_size: str
    company_size_raw: str
    tags: list[str]
    description: str
    source_url: str


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def parse_monthly_salary(value: str) -> tuple[int | None, int | None]:
    text = value.replace(",", "").replace(" ", "")
    if not text or any(marker in text for marker in ("面议", "/天", "/时", "/次", "/周")):
        return None, None
    range_match = re.search(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(万|千|k|K|元)?", text)
    if not range_match:
        return None, None
    multiplier = {"万": 10000, "千": 1000, "k": 1000, "K": 1000}.get(
        range_match.group(3) or "元", 1
    )
    minimum = round(float(range_match.group(1)) * multiplier)
    maximum = round(float(range_match.group(2)) * multiplier)
    return minimum, maximum


def is_zero_or_unpaid_salary(
    salary_text: str,
    salary_min: int | None,
    salary_max: int | None,
) -> bool:
    text = salary_text.replace(",", "").replace(" ", "").casefold()
    if any(marker in text for marker in ("无薪", "零薪", "0薪")):
        return True
    if salary_min is not None and salary_min <= 0:
        return True
    return bool(re.search(r"(?:^|[^\d.])0(?:\.0+)?元(?:/月)?(?:$|[^\d])", text))


def normalise_company_size(value: str) -> str:
    text = value.replace(" ", "")
    if not text:
        return ""
    if "20人以下" in text or "20-99人" in text or "100-299人" in text:
        return "中小企业"
    if any(marker in text for marker in ("300-499人", "500-999人", "1000-9999人", "10000人以上")):
        return "中大型企业"
    return text


def canonical_job_url(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if not host:
        return value
    scheme = "https" if host.endswith("zhaopin.com") else parsed.scheme
    return urlunparse((scheme, parsed.netloc, parsed.path, "", "", ""))


def _close_target(bridge: BrowserBridge, target_id: str) -> None:
    close = getattr(bridge, "close_target", None)
    if callable(close):
        try:
            close(target_id)
        except BrowserBridgeError:
            pass


def _search_url_for_query(bridge: BrowserBridge, query: str) -> str:
    target_id = bridge.open_url("https://www.zhaopin.com/")
    query_json = json.dumps(query, ensure_ascii=True)
    set_script = f"""(() => {{
      const input = document.querySelector('.search-wrapper__input');
      if (!input) return {{ search_url: '', logged_in: false, reason: 'search_input_not_found' }};
      const query = {query_json};
      input.focus();
      input.select();
      const inserted = document.execCommand('insertText', false, query);
      if (!inserted || input.value !== query) {{
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        setter.call(input, query);
        input.dispatchEvent(new InputEvent('input', {{ bubbles: true, data: query, inputType: 'insertText' }}));
      }}
      input.dispatchEvent(new Event('change', {{ bubbles: true }}));
      return {{
        search_url: document.querySelector('.search-wrapper__button')?.href || '',
        input_value: input.value || '',
        logged_in: Boolean(document.querySelector('.c-login__top__name')),
      }};
    }})()"""
    read_script = """(() => ({
      search_url: document.querySelector('.search-wrapper__button')?.href || '',
      input_value: document.querySelector('.search-wrapper__input')?.value || '',
      logged_in: Boolean(document.querySelector('.c-login__top__name')),
      reason: document.querySelector('.search-wrapper__input') ? '' : 'search_input_not_found',
    }))() // search-wrapper__input"""
    history_script = f"""(() => {{
      const query = {query_json};
      const item = [...document.querySelectorAll('.search-wrapper__word__history__a')]
        .find((candidate) => (candidate.innerText || '').trim() === query);
      if (!item) return {{ clicked: false }};
      item.click();
      return {{ clicked: true }};
    }})() // search-wrapper__word__history__a"""
    try:
        time.sleep(1.0)
        result: dict[str, object] = {}
        for _ in range(3):
            result = _as_dict(bridge.evaluate(target_id, set_script))
            for _ in range(4):
                time.sleep(0.5)
                current = _as_dict(bridge.evaluate(target_id, read_script))
                if current.get("search_url"):
                    result = current
                if "/kw" in str(current.get("search_url", "")):
                    break
            if "/kw" in str(result.get("search_url", "")):
                break
        if "/kw" not in str(result.get("search_url", "")):
            history = _as_dict(bridge.evaluate(target_id, history_script))
            if history.get("clicked"):
                time.sleep(0.8)
                result = _as_dict(bridge.evaluate(target_id, read_script))
        search_url = str(result.get("search_url", ""))
        if "/sou/" not in search_url or "/kw" not in search_url:
            raise BrowserBridgeError("智联招聘未接受本次搜索关键词，请刷新官网首页后重试")
        return search_url
    finally:
        _close_target(bridge, target_id)


def _page_url(search_url: str, page: int) -> str:
    base = re.sub(r"/p\d+$", "", search_url.rstrip("/"))
    return f"{base}/p{page}"


def _apply_city_filter(
    bridge: BrowserBridge,
    search_url: str,
    city: str,
) -> str:
    verified_city_codes = {"重庆": "551"}
    city_code = verified_city_codes.get(city)
    if city_code:
        return re.sub(r"/jl\d+", f"/jl{city_code}", search_url)
    target_id = bridge.open_url(_page_url(search_url, 1))
    city_json = json.dumps(city, ensure_ascii=True)
    open_script = """(() => {
      const control = document.querySelector('.query-location .content-s__item');
      if (!control) return { opened: false };
      control.click();
      return { opened: true };
    })() // query-location"""
    select_script = f"""(() => {{
      const city = {city_json};
      const option = [...document.querySelectorAll('.query-city .list__item__text')]
        .find((item) => (item.innerText || '').trim() === city);
      if (!option) return {{ clicked: false, url: location.href }};
      option.click();
      return {{ clicked: true, url: location.href }};
    }})() // query-city"""
    read_script = """(() => ({
      url: location.href,
      selected_city: (document.querySelector('.query-location .content-s__item__text')?.innerText || '').trim(),
    }))()"""
    try:
        opened: dict[str, object] = {}
        for _ in range(6):
            time.sleep(0.5)
            opened = _as_dict(bridge.evaluate(target_id, open_script))
            if opened.get("opened"):
                break
        if not opened.get("opened"):
            raise BrowserBridgeError("智联招聘地点筛选入口不可用")
        selected: dict[str, object] = {}
        for _ in range(5):
            time.sleep(0.4)
            selected = _as_dict(bridge.evaluate(target_id, select_script))
            if selected.get("clicked"):
                break
        if not selected.get("clicked"):
            raise BrowserBridgeError(f"智联招聘地点筛选中未找到“{city}”")
        filtered_url = str(selected.get("url", ""))
        if not filtered_url or filtered_url == _page_url(search_url, 1):
            time.sleep(1.5)
            result = _as_dict(bridge.evaluate(target_id, read_script))
            filtered_url = str(result.get("url", ""))
        if not filtered_url or filtered_url == _page_url(search_url, 1):
            raise BrowserBridgeError(f"智联招聘未应用“{city}”地点筛选")
        return filtered_url
    finally:
        _close_target(bridge, target_id)


def _extract_search_page(bridge: BrowserBridge, target_id: str) -> dict[str, object]:
    script = r"""(() => ({
      url: location.href,
      verification_required: /安全验证|Security Verification|访问验证/.test(document.body?.innerText || ''),
      items: [...document.querySelectorAll('.joblist-box__item')].map((card) => {
        const clean = (value) => (value || '').trim().replace(/\s+/g, ' ');
        const other = [...card.querySelectorAll('.jobinfo__other-info-item')].map((item) => clean(item.innerText));
        const companyTags = [...card.querySelectorAll('.companyinfo__tag .joblist-box__item-tag')].map((item) => clean(item.innerText));
        return {
          title: clean(card.querySelector('.jobinfo__name')?.innerText),
          company_name: clean(card.querySelector('.companyinfo__name')?.innerText),
          city: other[0] || '',
          experience_required: other[1] || '',
          degree_required: other[2] || '',
          salary_text: clean(card.querySelector('.jobinfo__salary')?.innerText),
          company_size_raw: companyTags.find((item) => /人/.test(item)) || '',
          tags: [...card.querySelectorAll('.jobinfo__tag .joblist-box__item-tag')].map((item) => clean(item.innerText)).filter(Boolean),
          source_url: card.querySelector('.jobinfo__name')?.href || '',
        };
      }).filter((item) => item.title && item.source_url),
    }))()"""
    return _as_dict(bridge.evaluate(target_id, script))


def search_jobs(
    bridge: BrowserBridge,
    query: str,
    page_limit: int,
    city: str,
) -> tuple[str, list[ZhaopinSearchJob]]:
    search_url = _search_url_for_query(bridge, query)
    search_url = _apply_city_filter(bridge, search_url, city)
    collected: dict[str, ZhaopinSearchJob] = {}
    for page in range(1, page_limit + 1):
        target_id = bridge.open_url(_page_url(search_url, page))
        try:
            time.sleep(1.0)
            payload = _extract_search_page(bridge, target_id)
            if payload.get("verification_required"):
                raise BrowserBridgeError("智联招聘要求人工安全验证，请在 Edge 完成后重试")
            items = payload.get("items", [])
            if not isinstance(items, list) or not items:
                break
            for raw in items:
                if not isinstance(raw, dict):
                    continue
                source_url = canonical_job_url(str(raw.get("source_url", "")))
                salary_text = str(raw.get("salary_text", ""))
                salary_min, salary_max = parse_monthly_salary(salary_text)
                tags = [str(item) for item in raw.get("tags", []) if str(item).strip()]
                company_size_raw = str(raw.get("company_size_raw", ""))
                collected[source_url] = ZhaopinSearchJob(
                    title=str(raw.get("title", "")).strip(),
                    company_name=str(raw.get("company_name", "")).strip(),
                    city=str(raw.get("city", "")).strip(),
                    salary_text=salary_text,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    degree_required=str(raw.get("degree_required", "")).strip(),
                    experience_required=str(raw.get("experience_required", "")).strip(),
                    company_size=normalise_company_size(company_size_raw),
                    company_size_raw=company_size_raw,
                    tags=tags,
                    description="、".join(tags),
                    source_url=source_url,
                )
        finally:
            _close_target(bridge, target_id)
    return search_url, list(collected.values())


def load_job_description(bridge: BrowserBridge, source_url: str) -> str:
    target_id = bridge.open_url(source_url)
    script = """(() => ({
      description: (document.querySelector('.describtion-card__detail-content')?.innerText || '').trim(),
      page_title: document.title,
      verification_required: /安全验证|Security Verification|访问验证/.test(document.body?.innerText || ''),
    }))()"""
    try:
        for _ in range(8):
            time.sleep(0.5)
            payload = _as_dict(bridge.evaluate(target_id, script))
            if payload.get("verification_required"):
                return ""
            description = str(payload.get("description", "")).strip()
            if description:
                return description
        return ""
    finally:
        _close_target(bridge, target_id)
