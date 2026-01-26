"""
Accounting Regulations Data

Provides structured accounting regulations data for RAG integration.
Covers: Hong Kong, China (PRC), and Canada

Data Sources:
- Hong Kong: HKICPA, Companies Ordinance (Cap. 622)
- China: Accounting Law of PRC, ASBE Standards
- Canada: CPA Canada Handbook, IFRS/ASPE

Last Updated: January 2026
"""

import logging
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class RegulationDocument:
    """Represents an accounting regulation document"""
    id: str
    jurisdiction: str
    title: str
    title_local: str  # Local language title
    category: str
    content: str
    effective_date: str
    last_updated: str
    source_url: str
    authority: str
    keywords: List[str]
    language: str


# ============================================================
# HONG KONG (香港) ACCOUNTING REGULATIONS
# ============================================================

HONG_KONG_REGULATIONS: List[Dict[str, Any]] = [
    {
        "id": "hk_companies_ordinance_622",
        "jurisdiction": "Hong Kong",
        "title": "Companies Ordinance (Cap. 622) - Financial Reporting Requirements",
        "title_local": "公司條例（第622章）- 財務報告規定",
        "category": "Primary Legislation",
        "content": """
Companies Ordinance (Cap. 622) - Financial Reporting Requirements for Hong Kong

1. GENERAL REQUIREMENTS
- Every company incorporated in Hong Kong must prepare annual financial statements
- Directors are responsible for ensuring financial statements give a true and fair view
- Financial statements must comply with applicable accounting standards

2. ACCOUNTING RECORDS (Part 9, Division 4)
- Companies must keep accounting records that:
  a) Sufficiently explain the company's transactions
  b) Enable the company's financial position to be determined with reasonable accuracy
  c) Allow financial statements to be prepared in accordance with the Ordinance
- Records must be kept for at least 7 years from the end of the financial year

3. ANNUAL FINANCIAL STATEMENTS (Part 9, Division 4)
- Must include: Balance sheet, Profit and loss account, Cash flow statement
- Directors must sign the financial statements
- Financial statements must be audited (with exemptions for small companies)

4. SMALL COMPANY EXEMPTIONS (Part 9, Division 2)
A company qualifies as a "small company" if it satisfies any two of:
- Total annual revenue not exceeding HKD 100 million
- Total assets not exceeding HKD 100 million
- Number of employees not exceeding 100

5. REPORTING EXEMPTIONS FOR ELIGIBLE PRIVATE COMPANIES
- May adopt simplified financial reporting
- Must comply with SME-FRF & SME-FRS (Small and Medium-sized Entity Financial Reporting)

6. DIRECTORS' REPORT REQUIREMENTS
- Business review including: business operations, performance analysis
- Discussion of principal risks and uncertainties
- Environmental, social, and governance (ESG) disclosures encouraged

7. AUDITOR REQUIREMENTS
- Must be a certified public accountant (CPA) registered with HKICPA
- Auditor must be independent
- Rotation requirements for listed companies
""",
        "effective_date": "2014-03-03",
        "last_updated": "2025-12-01",
        "source_url": "https://www.elegislation.gov.hk/hk/cap622",
        "authority": "Hong Kong SAR Government",
        "keywords": ["financial statements", "directors report", "audit", "small company exemption", "accounting records"],
        "language": "en"
    },
    {
        "id": "hk_hkfrs_overview",
        "jurisdiction": "Hong Kong",
        "title": "Hong Kong Financial Reporting Standards (HKFRS) Overview",
        "title_local": "香港財務報告準則（HKFRS）概覽",
        "category": "Accounting Standards",
        "content": """
Hong Kong Financial Reporting Standards (HKFRS) - Comprehensive Overview

INTRODUCTION
HKFRS are accounting standards issued by the Hong Kong Institute of Certified Public Accountants (HKICPA).
They are fully converged with International Financial Reporting Standards (IFRS).

APPLICABILITY
- All listed companies on HKEX must use HKFRS
- Private companies may choose between HKFRS and SME-FRF & SME-FRS
- Non-profit organizations may use HKFRS or specific sector guidelines

KEY STANDARDS (as of 2026)

HKFRS 1: First-time Adoption of HKFRS
- Provides framework for entities transitioning to HKFRS
- Allows certain exemptions and mandatory exceptions

HKFRS 9: Financial Instruments
- Classification and measurement of financial assets/liabilities
- Expected credit loss model for impairment
- Hedge accounting provisions

HKFRS 15: Revenue from Contracts with Customers
- Five-step model for revenue recognition
- Identification of performance obligations
- Variable consideration and contract modifications

HKFRS 16: Leases
- Single lessee accounting model
- Right-of-use asset and lease liability recognition
- Exceptions for short-term and low-value leases

HKFRS 17: Insurance Contracts
- Effective from 2023 reporting periods
- Building block approach for measurement
- Contractual service margin requirements

SME-FRF & SME-FRS (Small and Medium-sized Entities)
- Simplified framework for eligible private companies
- Reduced disclosure requirements
- Cost-based measurements preferred

RECENT UPDATES (2025-2026)
- HKFRS S1 & S2: Sustainability Disclosure Standards
- Aligned with ISSB standards
- Climate-related disclosures mandatory for listed companies from 2025
""",
        "effective_date": "2005-01-01",
        "last_updated": "2026-01-01",
        "source_url": "https://www.hkicpa.org.hk/en/Standards-setting/Standards",
        "authority": "Hong Kong Institute of Certified Public Accountants (HKICPA)",
        "keywords": ["HKFRS", "IFRS", "accounting standards", "SME-FRS", "financial reporting", "sustainability disclosure"],
        "language": "en"
    },
    {
        "id": "hk_afrc_ordinance",
        "jurisdiction": "Hong Kong",
        "title": "Accounting and Financial Reporting Council Ordinance (Cap. 588)",
        "title_local": "會計及財務匯報局條例（第588章）",
        "category": "Regulatory Framework",
        "content": """
Accounting and Financial Reporting Council Ordinance (Cap. 588)

OVERVIEW
The AFRC (formerly FRC) is Hong Kong's independent auditor oversight body.
Reformed in 2019 to take over responsibilities from HKICPA.

KEY FUNCTIONS
1. Registration of Public Interest Entity (PIE) Auditors
2. Inspection and investigation of PIE audits
3. Disciplinary actions against non-compliant auditors
4. Standard setting oversight

PIE AUDITOR REQUIREMENTS
- Must be registered with AFRC
- Subject to inspection regime
- Continuing professional development (CPD) requirements
- Quality control standards compliance

INSPECTION REGIME
- Annual inspections for auditors of major listed entities
- Risk-based inspections for other PIE auditors
- Inspection reports published for transparency

DISCIPLINARY FRAMEWORK
- Penalties include fines, suspension, removal from register
- Appeals to independent tribunal
- Public interest considerations

ANTI-MONEY LAUNDERING (AML) REQUIREMENTS
- CPAs must comply with AML/CFT requirements
- Customer due diligence obligations
- Suspicious transaction reporting
""",
        "effective_date": "2006-12-01",
        "last_updated": "2025-06-01",
        "source_url": "https://www.afrc.org.hk",
        "authority": "Accounting and Financial Reporting Council",
        "keywords": ["AFRC", "auditor regulation", "PIE auditors", "inspection", "disciplinary"],
        "language": "en"
    }
]


# ============================================================
# CHINA (中國) ACCOUNTING REGULATIONS
# ============================================================

CHINA_REGULATIONS: List[Dict[str, Any]] = [
    {
        "id": "cn_accounting_law_2017",
        "jurisdiction": "China (PRC)",
        "title": "Accounting Law of the People's Republic of China (2017 Amendment)",
        "title_local": "中華人民共和國會計法（2017年修訂）",
        "category": "Primary Legislation",
        "content": """
中華人民共和國會計法（Accounting Law of the People's Republic of China）

第一章 總則（Chapter 1: General Provisions）

第一條 目的
為了規範會計行為，保證會計資料真實、完整，加強經濟管理和財務管理，
提高經濟效益，維護社會主義市場經濟秩序，制定本法。

Article 1: Purpose
To standardize accounting practices, ensure the authenticity and integrity of 
accounting information, strengthen economic and financial management, improve 
economic efficiency, and maintain the socialist market economic order.

第二章 會計核算（Chapter 2: Accounting）

第九條 記帳本位幣
會計核算以人民幣為記帳本位幣。
業務收支以人民幣以外的貨幣為主的單位，可以選定其中一種貨幣作為記帳本位幣，
但是編報的財務會計報告應當折算為人民幣。

Article 9: Functional Currency
Accounting shall be conducted in Renminbi (RMB) as the functional currency.
Entities whose business operations are mainly in foreign currencies may choose 
one such currency as their functional currency, but financial reports must be 
converted to RMB.

第三章 會計憑證和會計帳簿（Chapter 3: Accounting Vouchers and Books）

第十四條 原始憑證要求
- 必須符合國家統一的會計制度的規定
- 內容完整、手續齊備
- 經辦人員和會計機構負責人、會計主管人員簽名或者蓋章

Article 14: Requirements for Original Vouchers
- Must comply with national unified accounting system
- Complete content and proper procedures
- Signed or stamped by handlers and accounting supervisors

第十五條 會計帳簿
各單位發生的各項經濟業務事項應當在依法設置的會計帳簿上統一登記、核算，
不得違反本法和國家統一的會計制度的規定私設會計帳簿登記、核算。

Article 15: Accounting Books
All economic transactions must be recorded in legally established accounting 
books. Maintaining separate, unofficial accounting books is prohibited.

第四章 財務會計報告（Chapter 4: Financial Reports）

第二十條 財務會計報告構成
財務會計報告由會計報表、會計報表附註和財務情況說明書組成。

Article 20: Components of Financial Reports
Financial reports consist of financial statements, notes to statements, 
and financial condition explanations.

第五章 會計監督（Chapter 5: Accounting Supervision）

第二十七條 內部會計監督制度
各單位應當建立、健全本單位內部會計監督制度。

Article 27: Internal Accounting Supervision System
All entities must establish and improve internal accounting supervision systems.

檔案保存期限（Document Retention Requirements）
- 會計憑證：30年
- 會計帳簿：30年  
- 財務會計報告：永久保存（年度）/10年（月度、季度）

Document Retention Periods:
- Accounting vouchers: 30 years
- Accounting books: 30 years
- Financial reports: Permanent (annual) / 10 years (monthly, quarterly)
""",
        "effective_date": "2017-11-04",
        "last_updated": "2025-01-01",
        "source_url": "http://www.npc.gov.cn/wxzl/gongbao/2017-12/06/content_2034154.htm",
        "authority": "National People's Congress (全國人民代表大會)",
        "keywords": ["會計法", "accounting law", "記帳本位幣", "functional currency", "會計憑證", "會計監督"],
        "language": "zh-en"
    },
    {
        "id": "cn_asbe_standards",
        "jurisdiction": "China (PRC)",
        "title": "Chinese Accounting Standards for Business Enterprises (ASBE)",
        "title_local": "企業會計準則（ASBE）",
        "category": "Accounting Standards",
        "content": """
企業會計準則（Chinese Accounting Standards for Business Enterprises - ASBE）

概述（Overview）
ASBE是由中華人民共和國財政部發布的會計準則體系，
已與國際財務報告準則（IFRS）實現實質性趨同。

ASBE is the accounting standards system issued by the Ministry of Finance of PRC,
substantially converged with International Financial Reporting Standards (IFRS).

準則體系結構（Standards Framework）

基本準則（Basic Standard）
- 會計假設：持續經營、會計分期、貨幣計量
- 會計原則：權責發生制、配比原則、實質重於形式
- 會計要素：資產、負債、所有者權益、收入、費用、利潤

Basic Standard covers:
- Accounting assumptions: going concern, accounting periods, monetary measurement
- Accounting principles: accrual basis, matching principle, substance over form
- Accounting elements: assets, liabilities, equity, revenue, expenses, profit

具體準則（Specific Standards）- 主要準則

CAS 1: 存貨（Inventories）
- 初始計量：成本
- 期末計量：成本與可變現淨值孰低

CAS 6: 無形資產（Intangible Assets）
- 研究階段支出費用化
- 開發階段支出資本化（滿足條件時）

CAS 14: 收入（Revenue）
- 2017年修訂，與IFRS 15趨同
- 五步法收入確認模型

CAS 21: 租賃（Leases）
- 2018年修訂，與IFRS 16趨同
- 單一承租人會計模型

CAS 22: 金融工具確認和計量（Financial Instruments）
- 2017年修訂，與IFRS 9趨同
- 預期信用損失模型

與IFRS的主要差異（Key Differences from IFRS）

1. 政府補助（Government Grants）
- 中國準則允許更多遞延確認選項
- IFRS傾向於立即確認

2. 關聯方披露（Related Party Disclosures）
- 中國準則要求更詳細披露
- 國有企業特殊規定

3. 合併報表範圍（Consolidation Scope）
- 對結構化主體的控制判斷可能不同
- 國有企業間交易特殊處理

上市公司額外要求（Additional Requirements for Listed Companies）
- 中國證監會（CSRC）額外披露要求
- 季度報告義務
- 內部控制審計要求
""",
        "effective_date": "2006-02-15",
        "last_updated": "2026-01-01",
        "source_url": "http://kjs.mof.gov.cn/zhuantilanmu/kuaijizhuanzhi/",
        "authority": "Ministry of Finance of PRC (財政部)",
        "keywords": ["企業會計準則", "ASBE", "IFRS convergence", "收入確認", "金融工具", "租賃準則"],
        "language": "zh-en"
    },
    {
        "id": "cn_cpa_law",
        "jurisdiction": "China (PRC)",
        "title": "Law on Certified Public Accountants of the People's Republic of China",
        "title_local": "中華人民共和國註冊會計師法",
        "category": "Professional Regulation",
        "content": """
中華人民共和國註冊會計師法（Law on Certified Public Accountants）

第一章 總則

第一條 立法目的
為了發揮註冊會計師在社會經濟活動中的鑒證和服務作用，
加強對註冊會計師的管理，維護社會公共利益和投資者的合法權益。

Article 1: Legislative Purpose
To utilize the attestation and service functions of CPAs in social and economic 
activities, strengthen CPA management, and protect public and investor interests.

第二章 考試和註冊

第七條 CPA考試
全國統一考試科目：
- 會計
- 審計
- 財務成本管理
- 公司戰略與風險管理
- 經濟法
- 稅法

Article 7: CPA Examination
National uniform examination subjects:
- Accounting
- Auditing  
- Financial Cost Management
- Corporate Strategy and Risk Management
- Economic Law
- Tax Law

第三章 業務

第十四條 業務範圍
（一）審查企業會計報表，出具審計報告
（二）驗證企業資本，出具驗資報告
（三）辦理企業合併、分立、清算事宜中的審計業務
（四）法律、行政法規規定的其他審計業務

Article 14: Scope of Practice
1. Audit enterprise financial statements and issue audit reports
2. Verify enterprise capital and issue verification reports
3. Conduct audits for mergers, divisions, and liquidations
4. Other audit services as required by laws and regulations

第四章 會計師事務所

第二十三條 設立條件
- 有5名以上的註冊會計師
- 有固定的辦公場所
- 有健全的內部管理制度

Article 23: Establishment Requirements
- At least 5 registered CPAs
- Fixed office premises
- Sound internal management systems

第五章 法律責任

第三十九條 法律責任
註冊會計師違反本法規定，故意出具虛假的審計報告、驗資報告：
- 構成犯罪的，依法追究刑事責任
- 尚不構成犯罪的，由省級財政部門予以警告，可並處5萬元以下罰款

Article 39: Legal Liability
CPAs who intentionally issue false audit or verification reports:
- Criminal liability if constituting a crime
- Warning and fines up to RMB 50,000 if not constituting a crime
""",
        "effective_date": "1993-10-31",
        "last_updated": "2014-08-31",
        "source_url": "http://www.cicpa.org.cn",
        "authority": "Chinese Institute of Certified Public Accountants (CICPA)",
        "keywords": ["註冊會計師", "CPA", "審計", "audit", "會計師事務所", "accounting firm"],
        "language": "zh-en"
    }
]


# ============================================================
# CANADA ACCOUNTING REGULATIONS
# ============================================================

CANADA_REGULATIONS: List[Dict[str, Any]] = [
    {
        "id": "ca_cpa_handbook_overview",
        "jurisdiction": "Canada",
        "title": "CPA Canada Handbook - Accounting Overview",
        "title_local": "CPA Canada Handbook - Comptabilité",
        "category": "Accounting Standards",
        "content": """
CPA Canada Handbook - Accounting Standards Framework

OVERVIEW
The CPA Canada Handbook contains Canadian accounting and auditing standards.
It is maintained by CPA Canada and the Accounting Standards Board (AcSB).

FRAMEWORK STRUCTURE

Part I: International Financial Reporting Standards (IFRS)
- Mandatory for publicly accountable enterprises
- Listed companies on TSX, TSXV
- Financial institutions, insurance companies
- Entities with public debt

Part II: Accounting Standards for Private Enterprises (ASPE)
- Available for private companies
- Simplified compared to IFRS
- Reduced disclosure requirements
- Cost-benefit considerations

Part III: Accounting Standards for Not-for-Profit Organizations (ASNPO)
- For registered charities and NPOs
- Modified basis of accounting allowed
- Fund accounting guidance

Part IV: Accounting Standards for Pension Plans
- For defined benefit and defined contribution plans
- Specialized measurement and disclosure requirements

IFRS ADOPTION IN CANADA (Since 2011)

Publicly Accountable Enterprises (PAEs) must apply IFRS:
- Entities with equity or debt traded in public markets
- Entities holding assets in fiduciary capacity for a broad group
- Banks, credit unions, insurance companies

Transition Guidance:
- First-time adoption relief available
- Comparative information requirements
- Opening balance sheet adjustments

ASPE KEY FEATURES (Section 1000-3870)

Section 1500: First-time Adoption of ASPE
Section 1520: Income Statement
Section 1521: Balance Sheet
Section 3031: Inventories (cost formulas, NRV testing)
Section 3061: Property, Plant and Equipment
Section 3064: Goodwill and Intangible Assets
Section 3065: Leases (operating vs finance lease model - differs from IFRS 16)
Section 3251: Equity
Section 3400: Revenue (earnings process model - differs from IFRS 15)
Section 3462: Employee Future Benefits
Section 3856: Financial Instruments

KEY DIFFERENCES: ASPE vs IFRS

1. Leases (Section 3065)
- ASPE: Traditional operating/finance lease classification
- IFRS 16: Single model, capitalize all leases

2. Revenue Recognition (Section 3400)
- ASPE: Earnings process model
- IFRS 15: Five-step contract model

3. Financial Instruments (Section 3856)
- ASPE: Simpler classification and measurement
- IFRS 9: Complex three-category model with ECL

4. Goodwill
- ASPE: Annual amortization (max 10 years)
- IFRS: No amortization, annual impairment test only
""",
        "effective_date": "2011-01-01",
        "last_updated": "2026-01-01",
        "source_url": "https://www.cpacanada.ca/en/business-and-accounting-resources/cpa-canada-handbook",
        "authority": "Chartered Professional Accountants of Canada (CPA Canada)",
        "keywords": ["CPA Canada Handbook", "IFRS", "ASPE", "private enterprise", "accounting standards"],
        "language": "en"
    },
    {
        "id": "ca_income_tax_act",
        "jurisdiction": "Canada",
        "title": "Income Tax Act - Accounting Requirements",
        "title_local": "Loi de l'impôt sur le revenu",
        "category": "Tax Legislation",
        "content": """
Income Tax Act (ITA) - Accounting and Record-Keeping Requirements

SECTION 230: RECORDS AND BOOKS

230(1) Records and Books
Every person carrying on business and every person who is required to pay or 
collect taxes or other amounts shall keep records and books of account at their 
place of business or residence in Canada.

Required Records:
- Books of account with supporting documentation
- Records necessary to determine tax obligations
- All invoices, receipts, and vouchers

230(4) Retention Period
Every person required to keep records shall retain them for:
- 6 years from the end of the last tax year to which they relate
- Indefinitely if there are unresolved tax matters or appeals

SECTION 249: FISCAL YEAR

249(1) Definition of Fiscal Year
- Generally 12 consecutive months
- May be less than 12 months for new corporations or on ceasing business
- Professional corporations may choose December 31 year-end

249.1: Alternative Method for Individuals
- Individuals may elect December 31 year-end for business income
- Special rules for partnerships

SECTION 12-20: INCOME COMPUTATION

Key Principles:
- Accrual method generally required for businesses
- Cash method available for farming and fishing
- Matching principle applies

12(1)(a) Income Inclusions
- Amounts receivable for goods and services
- Reserve recaptures
- Interest income

18(1) General Limitations on Deductions
- Must be incurred to earn income
- Capital expenditures not deductible (depreciation through CCA)
- Personal and living expenses not deductible

20(1) Deductions Permitted
- Capital cost allowance (CCA)
- Bad debt reserves
- Interest expense (subject to limitations)

CAPITAL COST ALLOWANCE (CCA) - SCHEDULE II

Key CCA Classes:
- Class 1 (4%): Buildings acquired after 1987
- Class 8 (20%): Office equipment, furniture
- Class 10 (30%): Motor vehicles
- Class 12 (100%): Computer software, small tools
- Class 50 (55%): Computer hardware

Accelerated Investment Incentive:
- First-year enhanced CCA available for certain properties
- Introduced 2018, phasing out by 2028

GST/HST CONSIDERATIONS

Registrant Requirements:
- Must register if taxable supplies exceed $30,000 in four consecutive quarters
- Input tax credits for GST/HST paid on business purchases
- Filing frequency based on annual revenue

Provincial Variations:
- GST only provinces: Alberta, Northwest Territories, Nunavut, Yukon
- HST provinces: Ontario (13%), Nova Scotia (15%), New Brunswick (15%), etc.
- PST + GST: British Columbia, Saskatchewan, Manitoba, Quebec (QST)
""",
        "effective_date": "1985-01-01",
        "last_updated": "2025-12-01",
        "source_url": "https://laws-lois.justice.gc.ca/eng/acts/I-3.3/",
        "authority": "Canada Revenue Agency (CRA)",
        "keywords": ["Income Tax Act", "record keeping", "CCA", "fiscal year", "GST/HST", "tax deductions"],
        "language": "en"
    },
    {
        "id": "ca_ontario_business_corporations_act",
        "jurisdiction": "Canada - Ontario",
        "title": "Ontario Business Corporations Act (OBCA) - Financial Provisions",
        "title_local": "Loi sur les sociétés par actions de l'Ontario",
        "category": "Corporate Legislation",
        "content": """
Ontario Business Corporations Act (OBCA) - Financial Statement Requirements

PART XI: FINANCIAL DISCLOSURE

Section 154: Annual Financial Statements

154(1) Requirement to Prepare
Directors shall place before shareholders at each annual meeting:
- Comparative financial statements as prescribed
- Report of the auditor, if any
- Such other information as required by regulations

154(2) Financial Statements Content
Must include:
a) Balance sheet
b) Statement of retained earnings
c) Income statement
d) Statement of changes in financial position
e) Notes to financial statements

Section 155: Audit Exemption

155(1) Exemption Available
A non-offering corporation may resolve not to appoint an auditor if:
- All shareholders consent in writing (annually)
- The corporation is not a subsidiary of a public corporation

Section 156: Qualifications of Auditor

156(1) Requirements
The auditor must be:
- Licensed under the Public Accounting Act, 2004
- Independent of the corporation
- Not an employee, director, or officer

Section 159: Auditor's Report

159(1) Report Requirements
The auditor shall report to shareholders on:
- Whether financial statements are prepared in accordance with GAAP
- Any reservation or qualification
- Consistency with prior year

PART XII: BOOKS AND RECORDS

Section 139: Corporate Records

139(1) Records Required
Every corporation shall prepare and maintain:
a) Articles and by-laws
b) Minutes of meetings and resolutions
c) Register of directors
d) Securities register
e) Adequate accounting records

139(5) Retention Period
Records shall be kept for:
- 6 years from the date of dissolution
- Or longer as required by other Acts

OFFERING CORPORATIONS (PUBLIC COMPANIES)

Additional requirements under:
- Ontario Securities Act
- National Instrument 51-102 (Continuous Disclosure)
- NI 52-109 (CEO/CFO Certification)
- NI 52-110 (Audit Committees)

PRIVATE COMPANY SIMPLIFICATIONS
- May use ASPE instead of IFRS
- Audit exemption available with shareholder consent
- Reduced continuous disclosure requirements
""",
        "effective_date": "1982-01-01",
        "last_updated": "2025-06-01",
        "source_url": "https://www.ontario.ca/laws/statute/90b16",
        "authority": "Government of Ontario",
        "keywords": ["OBCA", "financial statements", "audit exemption", "corporate records", "Ontario"],
        "language": "en"
    }
]


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def get_all_regulations() -> List[Dict[str, Any]]:
    """Get all accounting regulations from all jurisdictions"""
    return HONG_KONG_REGULATIONS + CHINA_REGULATIONS + CANADA_REGULATIONS


def get_regulations_by_jurisdiction(jurisdiction: str) -> List[Dict[str, Any]]:
    """Get regulations for a specific jurisdiction"""
    jurisdiction_lower = jurisdiction.lower()
    
    if "hong kong" in jurisdiction_lower or "hk" in jurisdiction_lower:
        return HONG_KONG_REGULATIONS
    elif "china" in jurisdiction_lower or "prc" in jurisdiction_lower or "中國" in jurisdiction_lower:
        return CHINA_REGULATIONS
    elif "canada" in jurisdiction_lower or "ontario" in jurisdiction_lower:
        return CANADA_REGULATIONS
    else:
        return []


def get_regulations_by_category(category: str) -> List[Dict[str, Any]]:
    """Get regulations by category"""
    all_regs = get_all_regulations()
    return [r for r in all_regs if category.lower() in r.get("category", "").lower()]


def prepare_for_rag_ingestion(regulations: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Prepare regulations for RAG vector database ingestion.
    
    Returns list of documents with content and metadata.
    """
    if regulations is None:
        regulations = get_all_regulations()
    
    documents = []
    
    for reg in regulations:
        # Build searchable content
        content_parts = [
            f"# {reg['title']}",
            f"## {reg['title_local']}" if reg.get('title_local') else "",
            f"Jurisdiction: {reg['jurisdiction']}",
            f"Category: {reg['category']}",
            f"Authority: {reg['authority']}",
            "",
            reg['content']
        ]
        
        content = "\n".join([p for p in content_parts if p])
        
        metadata = {
            "id": reg["id"],
            "jurisdiction": reg["jurisdiction"],
            "category": reg["category"],
            "title": reg["title"],
            "authority": reg["authority"],
            "effective_date": reg["effective_date"],
            "last_updated": reg["last_updated"],
            "source_url": reg["source_url"],
            "keywords": reg["keywords"],
            "language": reg["language"],
            "source": "accounting_regulations"
        }
        
        documents.append({
            "content": content,
            "metadata": metadata
        })
    
    return documents


async def ingest_regulations_to_rag(
    collection_name: str = "accounting",
    jurisdictions: List[str] = None
) -> Dict[str, Any]:
    """
    Ingest accounting regulations into the RAG system.
    
    Args:
        collection_name: Target collection name
        jurisdictions: List of jurisdictions to include (None = all)
    
    Returns:
        Ingestion result summary
    """
    try:
        from services.vectordb_manager import vectordb_manager
        
        # Get regulations
        if jurisdictions:
            regulations = []
            for j in jurisdictions:
                regulations.extend(get_regulations_by_jurisdiction(j))
        else:
            regulations = get_all_regulations()
        
        # Prepare for RAG
        documents = prepare_for_rag_ingestion(regulations)
        
        # Ingest
        success_count = 0
        for doc in documents:
            try:
                await vectordb_manager.add_document(
                    db_name=collection_name,
                    content=doc["content"],
                    metadata=doc["metadata"]
                )
                success_count += 1
            except Exception as e:
                logger.warning(f"Failed to ingest regulation {doc['metadata']['id']}: {e}")
        
        return {
            "success": True,
            "collection": collection_name,
            "total_regulations": len(regulations),
            "ingested": success_count,
            "jurisdictions": list(set(r["jurisdiction"] for r in regulations))
        }
        
    except Exception as e:
        logger.error(f"Error ingesting regulations: {e}")
        return {"success": False, "error": str(e)}


# Export for convenience
__all__ = [
    "HONG_KONG_REGULATIONS",
    "CHINA_REGULATIONS", 
    "CANADA_REGULATIONS",
    "get_all_regulations",
    "get_regulations_by_jurisdiction",
    "get_regulations_by_category",
    "prepare_for_rag_ingestion",
    "ingest_regulations_to_rag"
]
