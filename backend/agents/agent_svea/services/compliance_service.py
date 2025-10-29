"""
Agent Svea Compliance Service

Wraps existing Swedish compliance logic and integrations.
Provides clean interface for ADK agents to access compliance functionality.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ComplianceService:
    """
    Service for Swedish regulatory compliance and validation.
    
    Wraps existing functionality from:
    - swedish_compliance_integration.py
    - accounting/ directory (Swedish accounting rules)
    - Existing compliance validation logic from MCP server
    """
    
    def __init__(self):
        self.logger = logging.getLogger("svea.compliance_service")
        
        # Swedish compliance frameworks supported
        self.compliance_frameworks = [
            "GDPR", "Swedish_Accounting_Act", "BFL_Rules", "K_Reports",
            "SIE_Standard", "Skatteverket_Requirements", "Banking_Regulations"
        ]
        
        # BAS account validation rules
        self.bas_rules = {
            "account_length": 4,
            "account_types": {
                "1": "assets",
                "2": "liabilities", 
                "3": "revenue",
                "4": "expenses",
                "5": "expenses",
                "6": "expenses",
                "7": "expenses",
                "8": "financial"
            }
        }
        
        # Swedish VAT rates
        self.vat_rates = {
            "standard": 0.25,
            "reduced_12": 0.12,
            "reduced_6": 0.06,
            "exempt": 0.00
        }
        
        self.logger.info("Compliance Service initialized")
    
    async def validate_bas_account(self, account_number: str, account_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate BAS account number and structure.
        Reuses existing BAS validation logic from MCP server.
        """
        try:
            # Basic format validation
            if not account_number or len(account_number) != self.bas_rules["account_length"]:
                return {
                    "valid": False,
                    "error": "Invalid account number format",
                    "expected_format": f"{self.bas_rules['account_length']}-digit BAS account number"
                }
            
            # Numeric validation
            try:
                int(account_number)
            except ValueError:
                return {
                    "valid": False,
                    "error": "Account number must be numeric",
                    "expected_format": f"{self.bas_rules['account_length']}-digit numeric BAS account number"
                }
            
            # Account type validation
            first_digit = account_number[0]
            expected_type = self.bas_rules["account_types"].get(first_digit, "unknown")
            
            validation_result = {
                "valid": True,
                "account_number": account_number,
                "account_type": expected_type,
                "account_category": self._get_account_category(first_digit),
                "validation_method": "bas_rules",
                "confidence": "high"
            }
            
            # Check account type consistency if provided
            if account_type and account_type != expected_type:
                validation_result["warnings"] = [
                    f"Account type mismatch: expected {expected_type}, got {account_type}"
                ]
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"BAS account validation failed: {e}")
            return {"valid": False, "error": str(e)}
    
    async def validate_swedish_vat_number(self, vat_number: str) -> Dict[str, Any]:
        """
        Validate Swedish VAT number format.
        """
        try:
            # Swedish VAT format: SE + 12 digits
            if not vat_number.startswith("SE") or len(vat_number) != 14:
                return {
                    "valid": False,
                    "error": "Invalid Swedish VAT number format",
                    "expected_format": "SE + 12 digits (e.g., SE123456789012)"
                }
            
            # Validate numeric part
            numeric_part = vat_number[2:]
            try:
                int(numeric_part)
            except ValueError:
                return {
                    "valid": False,
                    "error": "VAT number must contain only digits after SE prefix"
                }
            
            return {
                "valid": True,
                "vat_number": vat_number,
                "country": "Sweden",
                "format": "SE + 12 digits",
                "validation_method": "format_check"
            }
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    async def calculate_swedish_vat(self, amount: float, vat_rate_type: str = "standard") -> Dict[str, Any]:
        """
        Calculate Swedish VAT based on amount and rate type.
        """
        try:
            if vat_rate_type not in self.vat_rates:
                return {
                    "error": f"Unknown VAT rate type: {vat_rate_type}",
                    "available_rates": list(self.vat_rates.keys())
                }
            
            vat_rate = self.vat_rates[vat_rate_type]
            vat_amount = amount * vat_rate
            total_amount = amount + vat_amount
            
            return {
                "net_amount": amount,
                "vat_rate": vat_rate,
                "vat_rate_percentage": vat_rate * 100,
                "vat_amount": round(vat_amount, 2),
                "total_amount": round(total_amount, 2),
                "vat_rate_type": vat_rate_type,
                "currency": "SEK"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def validate_sie_format(self, sie_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate SIE (Standard Import Export) format compliance.
        """
        try:
            required_fields = ["FLAGGA", "PROGRAM", "FORMAT", "GEN", "SIETYP"]
            missing_fields = []
            
            for field in required_fields:
                if field not in sie_data:
                    missing_fields.append(field)
            
            validation_result = {
                "valid": len(missing_fields) == 0,
                "sie_type": sie_data.get("SIETYP", "unknown"),
                "format_version": sie_data.get("FORMAT", "unknown"),
                "missing_fields": missing_fields,
                "validation_method": "sie_standard"
            }
            
            if not validation_result["valid"]:
                validation_result["error"] = f"Missing required SIE fields: {', '.join(missing_fields)}"
            
            # Additional SIE Type 4 specific validation
            if sie_data.get("SIETYP") == "4":
                type4_fields = ["KONTO", "VER", "TRANS"]
                missing_type4 = [field for field in type4_fields if field not in sie_data]
                if missing_type4:
                    validation_result["warnings"] = [
                        f"Missing SIE Type 4 fields: {', '.join(missing_type4)}"
                    ]
            
            return validation_result
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    async def check_gdpr_compliance(self, data_processing: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check GDPR compliance for data processing activities.
        """
        try:
            compliance_checks = {
                "lawful_basis": data_processing.get("lawful_basis") is not None,
                "consent_obtained": data_processing.get("consent_obtained", False),
                "data_minimization": data_processing.get("data_minimized", False),
                "purpose_limitation": data_processing.get("purpose_defined", False),
                "retention_policy": data_processing.get("retention_policy") is not None,
                "security_measures": data_processing.get("security_measures", []) != []
            }
            
            compliance_score = sum(compliance_checks.values()) / len(compliance_checks) * 100
            
            violations = []
            recommendations = []
            
            if not compliance_checks["lawful_basis"]:
                violations.append("Missing lawful basis for data processing")
                recommendations.append("Define and document lawful basis under GDPR Article 6")
            
            if not compliance_checks["consent_obtained"] and data_processing.get("lawful_basis") == "consent":
                violations.append("Consent required but not obtained")
                recommendations.append("Implement consent management system")
            
            if not compliance_checks["data_minimization"]:
                violations.append("Data minimization principle not applied")
                recommendations.append("Review and minimize data collection to necessary minimum")
            
            return {
                "compliant": compliance_score >= 80,
                "compliance_score": compliance_score,
                "checks_passed": compliance_checks,
                "violations": violations,
                "recommendations": recommendations,
                "data_subject_rights": [
                    "Right to access",
                    "Right to rectification", 
                    "Right to erasure",
                    "Right to data portability"
                ]
            }
            
        except Exception as e:
            return {"compliant": False, "error": str(e)}
    
    async def validate_skatteverket_report(self, report_data: Dict[str, Any], report_type: str) -> Dict[str, Any]:
        """
        Validate report format for Skatteverket submission.
        """
        try:
            validation_rules = {
                "vat_return": {
                    "required_fields": ["period", "sales_vat", "input_vat", "net_vat"],
                    "format": "XML",
                    "schema_version": "1.0"
                },
                "employer_report": {
                    "required_fields": ["period", "employees", "salary_total", "tax_deducted"],
                    "format": "XML", 
                    "schema_version": "2.1"
                },
                "annual_report": {
                    "required_fields": ["year", "revenue", "expenses", "profit_loss"],
                    "format": "PDF",
                    "schema_version": "1.2"
                }
            }
            
            if report_type not in validation_rules:
                return {
                    "valid": False,
                    "error": f"Unknown report type: {report_type}",
                    "supported_types": list(validation_rules.keys())
                }
            
            rules = validation_rules[report_type]
            missing_fields = []
            
            for field in rules["required_fields"]:
                if field not in report_data:
                    missing_fields.append(field)
            
            validation_result = {
                "valid": len(missing_fields) == 0,
                "report_type": report_type,
                "format": rules["format"],
                "schema_version": rules["schema_version"],
                "missing_fields": missing_fields
            }
            
            if not validation_result["valid"]:
                validation_result["error"] = f"Missing required fields: {', '.join(missing_fields)}"
            
            return validation_result
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def _get_account_category(self, first_digit: str) -> str:
        """Get Swedish account category name for BAS account."""
        categories = {
            "1": "Tillgångar (Assets)",
            "2": "Skulder (Liabilities)",
            "3": "Intäkter (Revenue)",
            "4": "Kostnader (Expenses)",
            "5": "Kostnader (Expenses)",
            "6": "Kostnader (Expenses)",
            "7": "Kostnader (Expenses)",
            "8": "Finansiella poster (Financial items)"
        }
        return categories.get(first_digit, "Okänd (Unknown)")
    
    async def get_compliance_status(self) -> Dict[str, Any]:
        """Get compliance service status."""
        return {
            "service": "compliance_service",
            "status": "active",
            "frameworks_supported": self.compliance_frameworks,
            "validation_capabilities": [
                "BAS account validation",
                "Swedish VAT number validation",
                "VAT calculation",
                "SIE format validation",
                "GDPR compliance checking",
                "Skatteverket report validation"
            ],
            "compliance_standards": {
                "accounting": "Swedish Accounting Act (Bokföringslagen)",
                "tax": "Skatteverket requirements",
                "data_protection": "GDPR",
                "financial_reporting": "BAS and SIE standards"
            }
        }