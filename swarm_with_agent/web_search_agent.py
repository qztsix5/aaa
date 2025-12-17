# baidu_search_agent.py - 优化版
import requests
from bs4 import BeautifulSoup
import urllib.parse
import asyncio
import logging
from typing import List, Dict
import re
import time

logger = logging.getLogger(__name__)

class BaiduSearchAgent:
    """使用百度搜索引擎的代理"""
    
    def __init__(self):
        self.base_url = "https://www.baidu.com/s"
        # 更新User-Agent
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def search_baidu(self, query: str, num_results: int = 8) -> List[Dict]:
        """使用百度搜索并解析结果"""
        try:
            # 编码查询参数
            params = {
                "wd": query,
                "rn": num_results,  # 结果数量
                "ie": "utf-8",
                "cl": 3,  # 网页类型
            }
            
            logger.info(f"搜索百度: {query}")
            response = self.session.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            results = self._parse_baidu_results_optimized(soup)
            
            return results
            
        except Exception as e:
            logger.error(f"百度搜索失败: {e}")
            # 返回模拟数据作为备用
            return self._get_fallback_results(query)
    
    def _parse_baidu_results_optimized(self, soup: BeautifulSoup) -> List[Dict]:
        """百度结果解析"""
        results = []
        
        # 尝试多种可能的选择器
        selectors = [
            'div.result',
            'div.c-container',
            'div[class*="result"]',
            'div[class*="c-container"]',
            'div.content-left',
            'div[srcid]'
        ]
        
        for selector in selectors:
            result_containers = soup.select(selector)
            if result_containers:
                logger.info(f"使用选择器 '{selector}' 找到 {len(result_containers)} 个结果")
                for container in result_containers[:10]:
                    try:
                        result = self._parse_single_result(container)
                        if result and result["title"]:
                            results.append(result)
                    except Exception as e:
                        logger.debug(f"解析单个结果失败: {e}")
                break  # 使用第一个有效的选择器
        
        # 如果没找到结果，尝试备用方法
        if not results:
            results = self._parse_backup_results(soup)
        
        # 去重
        seen_titles = set()
        unique_results = []
        for result in results:
            if result["title"] not in seen_titles:
                seen_titles.add(result["title"])
                unique_results.append(result)
        
        return unique_results[:8]  # 限制数量
    
    def _parse_single_result(self, container) -> Dict:
        """解析单个搜索结果"""
        # 提取标题
        title_elem = (container.find('h3') or 
                     container.find('a', class_=re.compile(r'title|head')) or
                     container.find('a'))
        
        if not title_elem:
            return None
            
        title = self._clean_text(title_elem.get_text())
        link = title_elem.get('href', '')
        
        # 处理百度跳转链接
        if link.startswith('/'):
            link = "https://www.baidu.com" + link
        
        # 优化摘要提取 - 尝试多种选择器
        abstract = self._extract_abstract_optimized(container)
        
        # 过滤广告
        if self._is_ad(container):
            return None
        
        return {
            "title": title,
            "link": link,
            "abstract": abstract,
            "source": "百度搜索"
        }
    
    def _extract_abstract_optimized(self, container) -> str:
        """优化摘要提取"""
        # 尝试多种摘要选择器
        abstract_selectors = [
            'div.c-abstract',
            'div.content',
            'div.desc',
            'div.summary',
            'span.content-right',
            'div[class*="abstract"]',
            'div[class*="desc"]',
            'div[class*="summary"]'
        ]
        
        for selector in abstract_selectors:
            abstract_elem = container.select_one(selector)
            if abstract_elem:
                abstract_text = self._clean_text(abstract_elem.get_text())
                if abstract_text and len(abstract_text) > 10:
                    return abstract_text
        
        # 如果上述选择器都失败，尝试从整个容器中提取非标题文本
        container_text = self._clean_text(container.get_text())
        title_elem = container.find('h3') or container.find('a')
        if title_elem:
            title_text = self._clean_text(title_elem.get_text())
            # 从完整文本中移除标题
            if title_text and title_text in container_text:
                abstract = container_text.replace(title_text, '').strip()
                if len(abstract) > 20:
                    return abstract
        
        return "暂无详细摘要"
    
    def _parse_backup_results(self, soup: BeautifulSoup) -> List[Dict]:
        """备用解析方法"""
        backup_results = []
        
        # 尝试查找所有包含链接的容器
        link_containers = soup.find_all(['div', 'section', 'article'], class_=True)
        
        for container in link_containers[:20]:
            try:
                link_elem = container.find('a', href=True)
                if not link_elem:
                    continue
                
                title = self._clean_text(link_elem.get_text())
                link = link_elem['href']
                
                if not title or len(title) < 5:
                    continue
                
                # 简单过滤广告
                if any(word in title.lower() for word in ['广告', '推广']):
                    continue
                
                # 提取容器内的文本作为摘要
                container_text = self._clean_text(container.get_text())
                abstract = container_text.replace(title, '').strip()
                abstract = self._clean_abstract(abstract)
                
                backup_results.append({
                    "title": title,
                    "link": link,
                    "abstract": abstract if abstract else "暂无详细摘要",
                    "source": "百度搜索(备用)"
                })
                    
            except Exception as e:
                continue
        
        return backup_results
    
    def _is_ad(self, container) -> bool:
        """判断是否为广告"""
        ad_indicators = ['广告', '推广', 'ad', 'advertisement']
        container_text = container.get_text().lower()
        return any(indicator in container_text for indicator in ad_indicators)
    
    def _clean_abstract(self, abstract: str) -> str:
        """清理摘要文本"""
        if not abstract:
            return ""
        
        # 移除过短的内容
        if len(abstract) < 10:
            return ""
        
        # 移除常见噪音
        noise_patterns = [
            r'百度快照.*',
            r'相关视频.*',
            r'广告',
            r'推广',
            r'查看更多',
            r'\.\.\.',
        ]
        
        for pattern in noise_patterns:
            abstract = re.sub(pattern, '', abstract)
        
        # 限制长度
        if len(abstract) > 200:
            abstract = abstract[:197] + "..."
        
        return abstract.strip()
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""
        # 替换多个空白字符为单个空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _get_fallback_results(self, query: str) -> List[Dict]:
        """获取备用结果（当搜索失败时使用）"""
        return [
            {
                "title": f"关于'{query}'的搜索结果",
                "link": "https://www.baidu.com",
                "abstract": f"由于网络或解析问题，无法获取'{query}'的实时搜索结果。建议直接访问百度搜索查看最新信息。",
                "source": "系统提示"
            }
        ]
    
    def format_search_results(self, results: List[Dict], query: str = "") -> str:
        """格式化搜索结果"""
        if not results:
            return f"🔍🔍 未找到关于'{query}'的相关结果"
        
        # 如果是备用结果，特殊处理
        if len(results) == 1 and results[0]["source"] == "系统提示":
            return f"【搜索提示】: {results[0]['abstract']}"
        
        formatted = f"【百度搜索: {query}】\n\n"
        
        for i, result in enumerate(results[:5], 1):
            formatted += f"{i}. 📰 {result['title']}\n"
            formatted += f"   摘要: {result['abstract']}\n"
            formatted += f"   来源: {result['source']}\n\n"
        
        # 添加财务搜索专用提示
        financial_keywords = ["财务", "财报", "收入", "利润", "年报", "季度报告"]
        if any(keyword in query for keyword in financial_keywords):
            formatted += "💡💡 财务信息提示: 以上信息来自公开搜索，请以公司官方公告为准"
        else:
            formatted += "💡💡 提示: 以上信息来自百度搜索，请谨慎参考其准确性"
        
        return formatted
    
    async def async_search(self, query: str) -> str:
        """异步搜索接口"""
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, self.search_baidu, query)
        return self.format_search_results(results, query)

# 创建全局实例
baidu_agent = BaiduSearchAgent()

# 适配原有接口的函数
async def search_market_info(query: str) -> str:
    """适配原有系统的搜索函数"""
    return await baidu_agent.async_search(query)

# 专门用于财务搜索的函数
async def search_financial_info(company: str, year: str = "") -> str:
    """搜索公司财务信息"""
    search_query = f"{company} {year}年 财务报告 年报" if year else f"{company} 最新财务数据"
    return await baidu_agent.async_search(search_query)
 