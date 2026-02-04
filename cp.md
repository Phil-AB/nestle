 ---                                                                                      
  📋 IMPLEMENTATION PLAN: Banking Account Opening Insights Report                          
                                                                                           
  Overview                                                                                 
                                                                                           
  We'll create a document generation template that:                                        
  1. Displays individual bank account opening form data                                    
  2. Generates insights from all applications in the database (average deposits,           
  demographics, trends)                                                                    
  3. Produces a professional DOCX/PDF report for banking demos                             
                                                                                           
  ---                                                                                      
  🎯 TASK BREAKDOWN                                                                        
                                                                                           
  Phase 1: Configuration Setup (Tasks 1-4)                                                 
                                                                                           
  Task 1: Document Type Configuration                                                      
  - Add bank_account_opening_form to config/document_types.yaml                            
  - Define fields: customer_name, account_type, initial_deposit, employment_status,        
  income_range, etc.                                                                       
  - This enables the extraction module to properly classify and store banking forms        
                                                                                           
  Task 2: Template Design                                                                  
  - Create Word document template with:                                                    
    - Customer Info Section: Name, ID, DOB, contact details                                
    - Account Details: Type, features, initial deposit, branch                             
    - Insights Section: Charts/tables showing aggregated analytics                         
  - Uses Jinja2 variables like {{customer_name}}, {{insights.average_deposit}}             
                                                                                           
  Task 3: Template Metadata                                                                
  - Create config/generation/templates/metadata/bank_account_insights_report.yaml          
  - Defines template properties, required/optional fields, capabilities                    
                                                                                           
  Task 4: Field Mapping Configuration                                                      
  - Create config/generation/templates/mappings/bank_account_insights_report.yaml          
  - Maps database fields → template variables                                              
  - Key Innovation: Defines calculated_fields for insights:                                
  calculated_fields:                                                                       
    average_deposit:                                                                       
      type: aggregate                                                                      
      sql: "SELECT AVG(CAST(fields->>'initial_deposit' AS DECIMAL)) FROM api_documents     
  WHERE document_type='bank_account_opening_form'"                                         
                                                                                           
    age_distribution:                                                                      
      type: group_by                                                                       
      sql: "SELECT age_group, COUNT(*) FROM ... GROUP BY age_group"                        
                                                                                           
  ---                                                                                      
  Phase 2: Backend Development (Tasks 5-6)                                                 
                                                                                           
  Task 5: Insights Calculation Service                                                     
  - Create modules/generation/services/banking_insights_service.py                         
  - Implements analytics queries:                                                          
    - Financial: Average deposit, median deposit, total applications                       
    - Demographics: Age groups (18-25, 26-35, 36-50, 50+), employment breakdown            
    - Product: Account type popularity                                                     
    - Geographic: Branch distribution                                                      
    - Trends: Monthly application volume                                                   
                                                                                           
  Task 6: Extend Data Provider                                                             
  - Enhance postgres_provider.py to support calculated insights                            
  - When mapping has calculated_fields, execute aggregate queries                          
  - Merge insights into data before rendering:                                             
  {                                                                                        
    "customer_name": "John Doe",        # Individual form data                             
    "account_type": "Savings",                                                             
    "initial_deposit": 5000,                                                               
    "insights": {                        # Aggregated analytics                            
      "average_deposit": 4250.50,                                                          
      "total_applications": 47,                                                            
      "age_distribution": {...}                                                            
    }                                                                                      
  }                                                                                        
                                                                                           
  ---                                                                                      
  Phase 3: Testing & Validation (Tasks 7-8)                                                
                                                                                           
  Task 7: Sample Data Creation                                                             
  - Create 10-20 test bank account records                                                 
  - Diverse data: different account types, ages, income levels, locations                  
  - Ensures meaningful insights for demo                                                   
                                                                                           
  Task 8: End-to-End Testing                                                               
  - Test complete flow:                                                                    
    a. Upload bank form → Extract fields → Store in DB                                     
    b. Call /api/v2/generation/generate                                                    
    c. Verify generated report has both individual data + insights                         
  - Validate calculations, formatting, edge cases                                          
                                                                                           
  ---                                                                                      
  Phase 4: Enhancement & Documentation (Tasks 9-10)                                        
                                                                                           
  Task 9: PDF Variant (Optional)                                                           
  - If DOCX isn't sufficient, create HTML→PDF version                                      
  - Better control over layout, charts, branding                                           
  - Uses HTMLPDFRenderer with WeasyPrint                                                   
                                                                                           
  Task 10: Demo Documentation                                                              
  - Create docs/BANKING_INSIGHTS_DEMO.md with:                                             
    - Demo script and talking points                                                       
    - API request/response examples                                                        
    - Value propositions for banking clients                                               
  - Prepare for Thursday discovery meeting                                                 
                                                                                           
  ---                                                                                      
  🏗️ TECHNICAL ARCHITECTURE                                                                
                                                                                           
  ┌─────────────────────────────────────────────────────────────┐                          
  │              BANKING INSIGHTS WORKFLOW                      │                          
  └─────────────────────────────────────────────────────────────┘                          
                                                                                           
  1. EXTRACTION (Already Built)                                                            
     Upload Bank Form → OCR (Reducto/Google) → Extract Fields                              
     → Store in api_documents table                                                        
                                                                                           
  2. INSIGHTS CALCULATION (New)                                                            
     Query database → Aggregate analytics → Calculate insights                             
     (average deposit, demographics, trends, etc.)                                         
                                                                                           
  3. DATA MERGING (New)                                                                    
     Individual form data + Global insights → Merged dataset                               
                                                                                           
  4. GENERATION (Existing Engine)                                                          
     Load template → Apply mapping → Render DOCX/PDF                                       
                                                                                           
  5. OUTPUT                                                                                
     Professional report with customer data + business insights                            
                                                                                           
  ---                                                                                      
  💡 KEY INSIGHTS FOR DEMO                                                                 
                                                                                           
  This approach showcases:                                                                 
                                                                                           
  1. OCR Capability: Extract structured data from unstructured forms                       
  2. Data Storage: Organized, queryable database records                                   
  3. Business Intelligence: Real-time analytics from accumulated data                      
  4. Document Automation: Professional reports without manual work                         
                                                                                           
  Value Proposition for Forms Capital:                                                     
  "Your team processes hundreds of account opening forms monthly. Our system extracts all  
  data automatically, stores it in a structured database, and generates executive reports  
  showing trends like 'average customer deposit increased 15% this quarter' or 'most       
  popular account type is savings among 25-35 age group'. This enables data-driven lending 
  decisions for products like Extra Cash and Extra Balance."                               
                                                                                           
  ---                                                                                      
  🔄 INTEGRATION WITH EXISTING SYSTEM                                                      
                                                                                           
  No Breaking Changes:                                                                     
  - Uses existing extraction module (OCR → database)                                       
  - Uses existing generation engine (template → document)                                  
  - Only adds:                                                                             
    - New document type configuration                                                      
    - New template files                                                                   
    - Insights calculation layer                                                           
                                                                                           
  Modular Design:                                                                          
  - Banking insights service is standalone                                                 
  - Can be reused for other analytics (loan applications, credit scoring, etc.)            
  - Calculated fields pattern is reusable for any domain                                   
                                                                                           
  ---                                                                                      
  ⏱️ DEVELOPMENT NOTES                                                                     
                                                                                           
  Critical Path:                                                                           
  1. Tasks 1-4 (Configuration) must complete first                                         
  2. Tasks 5-6 (Backend) depend on configuration                                           
  3. Task 7 (Sample data) enables Task 8 (Testing)                                         
  4. Task 9 (PDF) is optional/parallel                                                     
  5. Task 10 (Documentation) can happen anytime                                            
                                                                                           
  Priority for Thursday Demo:                                                              
  - Focus on Tasks 1-8 (core functionality)                                                
  - Task 9 (PDF) only if time permits                                                      
  - Task 10 (Documentation) should be done last                                            
                                                                                           
  ---                                                                                      
  Would you like me to start implementing these tasks? I can begin with Task #1 (creating  
  the document type configuration) and work through them systematically. The system is     
  already production-ready, so we're essentially:                                          
  1. Adding a new document type (config change)                                            
  2. Creating a new template (DOCX file + YAML configs)                                    
  3. Adding insights calculation logic (new service module)                                
                                                                                           
  This will integrate seamlessly with your existing architecture!                          
                                                                                           
✻ Sautéed for 2m 0s                                                                        
                                                                                           
❯ shouldnt the insights generation be able the particular user? or what better idea do     
  you have                                                                                 
                                                                                           
● Excellent catch! You're absolutely right - global insights (average of all applications) 
  aren't very useful for a banking demo. Let me propose a much better approach focused on  
  individual customer insights:                                                            
                                                                                           
  ---                                                                                      
  🎯 BETTER APPROACH: Individual Customer Insights & Risk Assessment                       
                                                                                           
  Instead of generic statistics, the report should provide actionable intelligence about   
  THIS specific customer, which is what a bank actually needs for:                         
  - Credit scoring/risk assessment                                                         
  - Product recommendations (Extra Cash, Extra Balance eligibility)                        
  - Automated decision support                                                             
  - Cross-selling opportunities                                                            
                                                                                           
  ---                                                                                      
  💡 REVISED INSIGHTS ARCHITECTURE                                                         
                                                                                           
  Option A: Individual + Comparative (RECOMMENDED)                                         
                                                                                           
  Generate insights specific to the customer, with comparative context:                    
                                                                                           
  {                                                                                        
    "customer_name": "John Doe",                                                           
    "account_type": "Savings",                                                             
    "initial_deposit": 5000,                                                               
    "employment_status": "Employed",                                                       
    "income_range": "50000-75000",                                                         
                                                                                           
    # INDIVIDUAL INSIGHTS (AI-powered assessment)                                          
    "insights": {                                                                          
      "risk_assessment": {                                                                 
        "risk_score": 72,              # 0-100 scale                                       
        "risk_level": "Low",            # Low/Medium/High                                  
        "creditworthiness": "Good",     # Poor/Fair/Good/Excellent                         
        "factors": {                                                                       
          "positive": ["Stable employment", "Above-average deposit", "Good income range"], 
          "concerns": ["Limited banking history", "First-time account holder"],            
          "recommendations": ["Build 6-month transaction history", "Consider savings       
  auto-deposit"]                                                                           
        }                                                                                  
      },                                                                                   
                                                                                           
      "product_eligibility": {                                                             
        "extra_cash": {                                                                    
          "eligible": true,                                                                
          "max_amount": 15000,                                                             
          "recommended_amount": 10000,                                                     
          "interest_rate": 12.5,                                                           
          "confidence": 0.85,                                                              
          "reasoning": "Stable income + good initial deposit + low debt indicators"        
        },                                                                                 
        "extra_balance": {                                                                 
          "eligible": true,                                                                
          "overdraft_limit": 5000,                                                         
          "monthly_fee": 50,                                                               
          "confidence": 0.78                                                               
        },                                                                                 
        "premium_account": {                                                               
          "eligible": true,                                                                
          "upgrade_recommended": true,                                                     
          "benefits": ["Free international transfers", "Higher interest rates"]            
        }                                                                                  
      },                                                                                   
                                                                                           
      "comparative_analysis": {                                                            
        "deposit_percentile": 68,       # This customer's deposit is higher than 68% of    
  similar customers                                                                        
        "age_group_avg_deposit": 3800,  # Average for 30-35 age group                      
        "income_bracket_approval_rate": 0.92,  # 92% approval rate for this income bracket 
        "similar_customer_profiles": {                                                     
          "total": 147,                                                                    
          "avg_loan_amount": 12500,                                                        
          "default_rate": 0.03                                                             
        }                                                                                  
      },                                                                                   
                                                                                           
      "recommendations": {                                                                 
        "account_upgrades": ["Premium Savings - Earns 2% more interest"],                  
        "cross_sell_products": ["Auto Loan", "Investment Account"],                        
        "next_steps": [                                                                    
          "Upload salary slip for higher credit limit",                                    
          "Link utility bill for address verification",                                    
          "Set up standing order to build transaction history"                             
        ]                                                                                  
      },                                                                                   
                                                                                           
      "automated_decisions": {                                                             
        "account_approval": "AUTO_APPROVE",   # AUTO_APPROVE/MANUAL_REVIEW/REJECT          
        "credit_pre_qualification": "APPROVED",                                            
        "tier_assignment": "Silver",                                                       
        "relationship_manager_needed": false                                               
      }                                                                                    
    }                                                                                      
  }                                                                                        
                                                                                           
  ---                                                                                      
  Option B: Pure Individual (Simpler for MVP)                                              
                                                                                           
  Focus only on THIS customer without comparisons:                                         
                                                                                           
  "insights": {                                                                            
    "risk_score": 72,                                                                      
    "credit_eligibility": {                                                                
      "extra_cash_max": 15000,                                                             
      "extra_balance_limit": 5000                                                          
    },                                                                                     
    "recommended_products": ["Premium Savings", "Auto Loan"],                              
    "approval_decision": "AUTO_APPROVE",                                                   
    "flags": []  # Empty = no issues                                                       
  }                                                                                        
                                                                                           
  ---                                                                                      
  Option C: Hybrid (Best for Demo)                                                         
                                                                                           
  Individual insights + key comparative benchmarks:                                        
                                                                                           
  "insights": {                                                                            
    # About THIS customer                                                                  
    "customer_profile": {                                                                  
      "risk_level": "Low",                                                                 
      "credit_score": 720,                                                                 
      "eligibility": {...}                                                                 
    },                                                                                     
                                                                                           
    # How they compare (adds context)                                                      
    "benchmarks": {                                                                        
      "deposit_vs_peers": "+25%",  # 25% above average for similar profiles                
      "approval_likelihood": "95%"  # Based on similar profiles                            
    }                                                                                      
  }                                                                                        
                                                                                           
  ---                                                                                      
  🔍 WHAT MAKES THIS BETTER?                                                               
                                                                                           
  For the Demo:                                                                            
  1. Shows AI Value: "Our system automatically assesses creditworthiness and recommends    
  loan amounts"                                                                            
  2. Actionable: Bank staff can immediately act on recommendations                         
  3. Personalized: Each customer gets tailored insights                                    
  4. Automated Decision Support: Reduces manual review time                                
                                                                                           
  For Forms Capital Use Case:                                                              
  - Extra Cash Product: "Customer qualifies for $15,000 Extra Cash loan based on income and
   deposit"                                                                                
  - Extra Balance Product: "Approve $5,000 overdraft protection"                           
  - Risk Management: "Low-risk customer - auto-approve account opening"                    
  - Cross-Sell: "Recommend investment account based on high initial deposit"               
                                                                                           
  ---                                                                                      
  🛠️ REVISED IMPLEMENTATION APPROACH                                                       
                                                                                           
  Task 5 Update: Implement Customer Insights Service                                       
                                                                                           
  Create modules/generation/services/customer_insights_service.py:                         
                                                                                           
  class CustomerInsightsService:                                                           
      """Generate personalized insights for individual customers."""                       
                                                                                           
      async def calculate_risk_score(self, customer_data: Dict) -> Dict:                   
          """                                                                              
          Calculate risk score using rules-based or ML model.                              
                                                                                           
          Factors:                                                                         
          - Employment status (weight: 30%)                                                
          - Income range (weight: 25%)                                                     
          - Initial deposit (weight: 20%)                                                  
          - Age (weight: 15%)                                                              
          - Account type (weight: 10%)                                                     
          """                                                                              
          score = 0                                                                        
                                                                                           
          # Employment scoring                                                             
          if customer_data.get('employment_status') == 'Employed':                         
              score += 30                                                                  
          elif customer_data.get('employment_status') == 'Self-Employed':                  
              score += 20                                                                  
                                                                                           
          # Income scoring                                                                 
          income = customer_data.get('income_range', '')                                   
          if '75000+' in income:                                                           
              score += 25                                                                  
          elif '50000-75000' in income:                                                    
              score += 20                                                                  
                                                                                           
          # Initial deposit scoring                                                        
          deposit = float(customer_data.get('initial_deposit', 0))                         
          if deposit >= 10000:                                                             
              score += 20                                                                  
          elif deposit >= 5000:                                                            
              score += 15                                                                  
          elif deposit >= 1000:                                                            
              score += 10                                                                  
                                                                                           
          # Age scoring (25-55 is prime)                                                   
          age = self._calculate_age(customer_data.get('date_of_birth'))                    
          if 25 <= age <= 55:                                                              
              score += 15                                                                  
          elif 18 <= age < 25 or 55 < age <= 65:                                           
              score += 10                                                                  
                                                                                           
          return {                                                                         
              "risk_score": score,                                                         
              "risk_level": self._score_to_level(score),                                   
              "creditworthiness": self._score_to_creditworthiness(score)                   
          }                                                                                
                                                                                           
      async def calculate_product_eligibility(self, customer_data: Dict, risk_score: int)  
  -> Dict:                                                                                 
          """Determine loan/product eligibility based on profile."""                       
                                                                                           
          income = self._parse_income_range(customer_data.get('income_range'))             
          deposit = float(customer_data.get('initial_deposit', 0))                         
                                                                                           
          # Extra Cash (Personal Loan) eligibility                                         
          extra_cash_eligible = risk_score >= 50 and income >= 30000                       
          max_loan = min(income * 0.3, 50000)  # Max 30% of annual income                  
                                                                                           
          # Extra Balance (Overdraft) eligibility                                          
          extra_balance_eligible = risk_score >= 60 and deposit >= 1000                    
          overdraft_limit = min(deposit * 2, 10000)                                        
                                                                                           
          return {                                                                         
              "extra_cash": {                                                              
                  "eligible": extra_cash_eligible,                                         
                  "max_amount": max_loan if extra_cash_eligible else 0,                    
                  "recommended_amount": max_loan * 0.7,  # Conservative recommendation     
                  "interest_rate": self._calculate_interest_rate(risk_score),              
                  "confidence": risk_score / 100                                           
              },                                                                           
              "extra_balance": {                                                           
                  "eligible": extra_balance_eligible,                                      
                  "overdraft_limit": overdraft_limit if extra_balance_eligible else 0,     
                  "monthly_fee": 50,                                                       
                  "confidence": risk_score / 100                                           
              }                                                                            
          }                                                                                
                                                                                           
      async def generate_recommendations(self, customer_data: Dict, risk_assessment: Dict) 
  -> Dict:                                                                                 
          """Generate personalized recommendations."""                                     
                                                                                           
          recommendations = {                                                              
              "account_upgrades": [],                                                      
              "cross_sell_products": [],                                                   
              "next_steps": []                                                             
          }                                                                                
                                                                                           
          deposit = float(customer_data.get('initial_deposit', 0))                         
          income = self._parse_income_range(customer_data.get('income_range'))             
                                                                                           
          # Account upgrade recommendations                                                
          if deposit >= 10000:                                                             
              recommendations["account_upgrades"].append("Premium Account - Higher interest
   rates")                                                                                 
                                                                                           
          # Cross-sell based on profile                                                    
          if income >= 50000:                                                              
              recommendations["cross_sell_products"].extend(["Investment Account", "Credit 
  Card"])                                                                                  
                                                                                           
          if customer_data.get('employment_status') == 'Employed':                         
              recommendations["cross_sell_products"].append("Payroll Direct Deposit")      
                                                                                           
          # Next steps                                                                     
          if risk_assessment['risk_score'] < 70:                                           
              recommendations["next_steps"].append("Upload proof of income for better      
  rates")                                                                                  
                                                                                           
          return recommendations                                                           
                                                                                           
  ---                                                                                      
  🎨 UPDATED TEMPLATE STRUCTURE                                                            
                                                                                           
  The Word template would have sections like:                                              
                                                                                           
  BANK ACCOUNT OPENING - INSIGHTS REPORT                                                   
  Generated: {{current_date}}                                                              
                                                                                           
  ─────────────────────────────────────                                                    
  1. CUSTOMER INFORMATION                                                                  
  ─────────────────────────────────────                                                    
  Name:              {{customer_name}}                                                     
  ID Number:         {{customer_id}}                                                       
  Date of Birth:     {{date_of_birth}}                                                     
  Employment:        {{employment_status}}                                                 
  Income Range:      {{income_range}}                                                      
  Initial Deposit:   {{initial_deposit | currency}}                                        
                                                                                           
  ─────────────────────────────────────                                                    
  2. RISK ASSESSMENT                                                                       
  ─────────────────────────────────────                                                    
  Risk Score:        {{insights.risk_score}}/100                                           
  Risk Level:        {{insights.risk_level}}                                               
  Creditworthiness:  {{insights.creditworthiness}}                                         
                                                                                           
  Positive Factors:                                                                        
  {% for factor in insights.risk_assessment.factors.positive %}                            
    ✓ {{factor}}                                                                           
  {% endfor %}                                                                             
                                                                                           
  Areas of Concern:                                                                        
  {% for concern in insights.risk_assessment.factors.concerns %}                           
    ⚠ {{concern}}                                                                          
  {% endfor %}                                                                             
                                                                                           
  ─────────────────────────────────────                                                    
  3. PRODUCT ELIGIBILITY                                                                   
  ─────────────────────────────────────                                                    
                                                                                           
  EXTRA CASH (Personal Loan)                                                               
    Status:          {% if insights.product_eligibility.extra_cash.eligible %}✓ ELIGIBLE{% 
  else %}✗ NOT ELIGIBLE{% endif %}                                                         
    Max Amount:      {{insights.product_eligibility.extra_cash.max_amount | currency}}     
    Recommended:     {{insights.product_eligibility.extra_cash.recommended_amount |        
  currency}}                                                                               
    Interest Rate:   {{insights.product_eligibility.extra_cash.interest_rate}}%            
    Confidence:      {{insights.product_eligibility.extra_cash.confidence * 100}}%         
                                                                                           
  EXTRA BALANCE (Overdraft Protection)                                                     
    Status:          {% if insights.product_eligibility.extra_balance.eligible %}✓         
  ELIGIBLE{% else %}✗ NOT ELIGIBLE{% endif %}                                              
    Overdraft Limit: {{insights.product_eligibility.extra_balance.overdraft_limit |        
  currency}}                                                                               
    Monthly Fee:     {{insights.product_eligibility.extra_balance.monthly_fee | currency}} 
                                                                                           
  ─────────────────────────────────────                                                    
  4. RECOMMENDATIONS                                                                       
  ─────────────────────────────────────                                                    
                                                                                           
  Recommended Products:                                                                    
  {% for product in insights.recommendations.cross_sell_products %}                        
    • {{product}}                                                                          
  {% endfor %}                                                                             
                                                                                           
  Next Steps:                                                                              
  {% for step in insights.recommendations.next_steps %}                                    
    → {{step}}                                                                             
  {% endfor %}                                                                             
                                                                                           
  ─────────────────────────────────────                                                    
  5. AUTOMATED DECISION                                                                    
  ─────────────────────────────────────                                                    
  Account Approval:  {{insights.automated_decisions.account_approval}}                     
  Credit Status:     {{insights.automated_decisions.credit_pre_qualification}}             
  Assigned Tier:     {{insights.automated_decisions.tier_assignment}}                      
                                                                                           
  ---                                                                                      
  🎯 WHICH OPTION SHOULD WE IMPLEMENT?                                                     
                                                                                           
  My Recommendation: Option C (Hybrid)                                                     
                                                                                           
  Implement individual insights with light comparative context:                            
  1. Primary Focus: THIS customer's risk score, eligibility, recommendations               
  2. Secondary Context: "How you compare" section with 2-3 benchmarks                      
  3. Why: Shows AI capability without overcomplicating the demo                            
                                                                                           
  Demo Flow:                                                                               
  1. "We uploaded a bank account opening form"                                             
  2. "System extracted all customer data automatically" (OCR capability)                   
  3. "AI analyzed the customer profile and calculated a risk score of 72/100"              
  4. "System recommends approving Extra Cash loan up to $15,000"                           
  5. "Customer qualifies for premium account upgrade"                                      
  6. "All decisions automated - no manual review needed"                                   
                                                                                           
  ---                                                                                      
  What do you think? Should we go with:                                                    
  - Option A: Individual + Comparative (most comprehensive)                                
  - Option B: Pure Individual (simplest)                                                   
  - Option C: Hybrid (balanced for demo)                                                   
                                                                                           
  Or do you have another angle in mind? I want to make sure this aligns with what will     
  impress Forms Capital on Thursday!                                                       
                                                                                           
✻ Sautéed for 51s                                                                          
                                                                                           
  10 tasks (0 done, 10 open) · ctrl+t to hide tasks                                        
  ◻ Create Bank Account Opening Form document type configuration                           
  ◻ Design banking insights template structure                                             
  ◻ Create template metadata configuration                                                 
  ◻ Create field mapping configuration                                                     
  ◻ Implement insights calculation service                                                 
  ◻ Extend data provider for calculated insights                                           
  ◻ Create sample bank account data for testing                                            
  ◻ Test generation endpoint with banking template                                         
  ◻ Create PDF variant of template (optional)                                              
  ◻ Document banking demo usage and prepare demo script                                    
                                                             