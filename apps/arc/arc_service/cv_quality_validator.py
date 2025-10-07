"""
CV Quality Validator
====================
Validates and enforces quality standards for generated CVs.
Provides detailed metrics and auto-correction capabilities.
"""

import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class CVQualityReport:
    """Detailed quality report for a generated CV."""
    
    def __init__(self):
        self.passed = True
        self.warnings = []
        self.errors = []
        self.metrics = {}
        self.recommendations = []
    
    def add_warning(self, message: str):
        self.warnings.append(message)
        logger.warning(f"[CV QUALITY] ⚠️ {message}")
    
    def add_error(self, message: str):
        self.errors.append(message)
        self.passed = False
        logger.error(f"[CV QUALITY] ❌ {message}")
    
    def add_metric(self, name: str, value: Any):
        self.metrics[name] = value
    
    def add_recommendation(self, message: str):
        self.recommendations.append(message)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "metrics": self.metrics,
            "recommendations": self.recommendations
        }
    
    def log_summary(self):
        """Log a summary of the quality report."""
        logger.info(f"[CV QUALITY] ===== QUALITY REPORT =====")
        logger.info(f"[CV QUALITY] Status: {'✅ PASSED' if self.passed else '❌ FAILED'}")
        logger.info(f"[CV QUALITY] Errors: {len(self.errors)}, Warnings: {len(self.warnings)}")
        logger.info(f"[CV QUALITY] Metrics: {self.metrics}")
        if self.errors:
            logger.error(f"[CV QUALITY] Critical Errors: {self.errors}")
        if self.recommendations:
            logger.info(f"[CV QUALITY] Recommendations: {self.recommendations}")


class CVQualityValidator:
    """Validates CV quality and enforces standards."""
    
    def __init__(self):
        # Configurable thresholds
        self.min_bullets_recent_roles = 5  # Recent roles (last 3 years)
        self.min_bullets_older_roles = 3   # Older roles
        self.max_bullets_per_role = 12
        self.recent_years_threshold = 3
    
    def validate_cv(
        self, 
        cv_data: Dict[str, Any], 
        original_profile: Dict[str, Any],
        job_description: str = None
    ) -> CVQualityReport:
        """
        Comprehensive CV validation.
        
        Args:
            cv_data: Generated CV data
            original_profile: Original profile data for comparison
            job_description: Optional job description for context
        
        Returns:
            CVQualityReport with validation results
        """
        report = CVQualityReport()
        
        # Extract work experience
        cv_roles = self._extract_roles(cv_data)
        profile_roles = original_profile.get("work_experience", [])
        
        # 1. CRITICAL: Role completeness
        self._validate_role_completeness(cv_roles, profile_roles, report)
        
        # 2. CRITICAL: Bullet point distribution
        self._validate_bullet_distribution(cv_roles, profile_roles, report)
        
        # 3. Role chronology
        self._validate_chronology(cv_roles, report)
        
        # 4. Content quality
        self._validate_content_quality(cv_data, report)
        
        # 5. Profile size metrics
        self._add_profile_metrics(profile_roles, cv_roles, report)
        
        report.log_summary()
        return report
    
    def auto_correct_cv(
        self,
        cv_data: Dict[str, Any],
        original_profile: Dict[str, Any],
        report: CVQualityReport
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Attempt to auto-correct CV issues.
        
        Returns:
            (corrected_cv_data, was_modified)
        """
        modified = False
        
        # Extract work experience
        if "cv" not in cv_data or "professional_experience" not in cv_data["cv"]:
            logger.error("[CV AUTO-CORRECT] Invalid CV structure, cannot auto-correct")
            return cv_data, False
        
        cv_roles = cv_data["cv"]["professional_experience"].get("roles", [])
        profile_roles = original_profile.get("work_experience", [])
        
        # 1. Add missing roles
        if len(cv_roles) < len(profile_roles):
            logger.info(f"[CV AUTO-CORRECT] Attempting to add {len(profile_roles) - len(cv_roles)} missing roles")
            cv_roles, roles_added = self._add_missing_roles(cv_roles, profile_roles)
            if roles_added:
                cv_data["cv"]["professional_experience"]["roles"] = cv_roles
                modified = True
                logger.info(f"[CV AUTO-CORRECT] ✅ Added {roles_added} missing roles")
        
        # 2. Ensure minimum bullet counts
        cv_roles, bullets_fixed = self._ensure_minimum_bullets(cv_roles, profile_roles)
        if bullets_fixed > 0:
            cv_data["cv"]["professional_experience"]["roles"] = cv_roles
            modified = True
            logger.info(f"[CV AUTO-CORRECT] ✅ Fixed bullet counts for {bullets_fixed} roles")
        
        # 3. Sort chronologically
        cv_roles, was_sorted = self._sort_roles_chronologically(cv_roles)
        if was_sorted:
            cv_data["cv"]["professional_experience"]["roles"] = cv_roles
            modified = True
            logger.info(f"[CV AUTO-CORRECT] ✅ Sorted roles chronologically")
        
        if modified:
            logger.info("[CV AUTO-CORRECT] ✅ CV was auto-corrected successfully")
        else:
            logger.info("[CV AUTO-CORRECT] No corrections needed")
        
        return cv_data, modified
    
    # ========== PRIVATE VALIDATION METHODS ==========
    
    def _extract_roles(self, cv_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract roles list from CV data."""
        try:
            return cv_data.get("cv", {}).get("professional_experience", {}).get("roles", [])
        except Exception:
            return []
    
    def _validate_role_completeness(
        self,
        cv_roles: List[Dict[str, Any]],
        profile_roles: List[Dict[str, Any]],
        report: CVQualityReport
    ):
        """Validate that all roles from profile are included in CV."""
        expected_count = len(profile_roles)
        actual_count = len(cv_roles)
        
        report.add_metric("expected_role_count", expected_count)
        report.add_metric("actual_role_count", actual_count)
        report.add_metric("role_completeness_pct", round((actual_count / expected_count * 100) if expected_count > 0 else 100, 1))
        
        if actual_count < expected_count:
            missing_count = expected_count - actual_count
            report.add_error(f"Missing {missing_count} roles ({actual_count}/{expected_count} included)")
            
            # Identify which companies are missing
            cv_companies = {self._normalize_company(r.get("company", "")) for r in cv_roles}
            profile_companies = [self._normalize_company(r.get("company_name", "")) for r in profile_roles]
            missing_companies = [c for c in profile_companies if c not in cv_companies]
            
            if missing_companies:
                report.add_metric("missing_companies", missing_companies[:5])  # First 5
                logger.error(f"[CV QUALITY] Missing companies: {missing_companies}")
        elif actual_count > expected_count:
            report.add_warning(f"CV has MORE roles than profile ({actual_count} vs {expected_count})")
        else:
            logger.info(f"[CV QUALITY] ✅ All {actual_count} roles included")
    
    def _validate_bullet_distribution(
        self,
        cv_roles: List[Dict[str, Any]],
        profile_roles: List[Dict[str, Any]],
        report: CVQualityReport
    ):
        """Validate bullet point distribution across roles."""
        if not cv_roles:
            report.add_error("No roles found in CV")
            return
        
        current_year = datetime.now().year
        bullet_issues = []
        
        for i, role in enumerate(cv_roles):
            company = role.get("company", f"Role {i+1}")
            bullets = role.get("bullets", [])
            
            # Handle both string arrays and object arrays
            if bullets and isinstance(bullets[0], dict):
                bullets = [b.get("content", "") for b in bullets if b.get("content")]
            
            bullet_count = len(bullets)
            
            # Determine if this is a recent role
            start_date = role.get("start_date", "")
            is_recent = self._is_recent_role(start_date, current_year)
            
            # Check minimum bullets
            min_expected = self.min_bullets_recent_roles if is_recent else self.min_bullets_older_roles
            
            if bullet_count < min_expected:
                issue = f"{company}: {bullet_count} bullets (expected ≥{min_expected})"
                bullet_issues.append(issue)
                
                if is_recent and i < 3:  # Top 3 roles
                    report.add_error(f"Top role '{company}' has only {bullet_count} bullets (expected ≥{min_expected})")
                else:
                    report.add_warning(f"Role '{company}' has only {bullet_count} bullets (expected ≥{min_expected})")
            elif bullet_count > self.max_bullets_per_role:
                report.add_warning(f"Role '{company}' has {bullet_count} bullets (max recommended: {self.max_bullets_per_role})")
        
        # Calculate average bullets
        total_bullets = sum(len(r.get("bullets", [])) for r in cv_roles)
        avg_bullets = round(total_bullets / len(cv_roles), 1) if cv_roles else 0
        report.add_metric("avg_bullets_per_role", avg_bullets)
        report.add_metric("total_bullets", total_bullets)
        
        if bullet_issues:
            report.add_metric("roles_with_insufficient_bullets", len(bullet_issues))
            logger.warning(f"[CV QUALITY] Bullet issues: {bullet_issues[:3]}")  # Log first 3
        else:
            logger.info(f"[CV QUALITY] ✅ Bullet distribution acceptable (avg: {avg_bullets} per role)")
    
    def _validate_chronology(self, cv_roles: List[Dict[str, Any]], report: CVQualityReport):
        """Validate that roles are in reverse chronological order."""
        if len(cv_roles) < 2:
            return
        
        is_sorted = True
        for i in range(len(cv_roles) - 1):
            current_date = self._parse_date_for_sort(cv_roles[i].get("start_date", ""))
            next_date = self._parse_date_for_sort(cv_roles[i + 1].get("start_date", ""))
            
            if current_date < next_date:
                is_sorted = False
                report.add_warning(f"Roles not in reverse chronological order (position {i+1}-{i+2})")
                break
        
        if is_sorted:
            logger.info("[CV QUALITY] ✅ Roles are in correct chronological order")
    
    def _validate_content_quality(self, cv_data: Dict[str, Any], report: CVQualityReport):
        """Validate content quality (placeholders, duplicates, etc.)."""
        cv_json = str(cv_data)
        
        # Check for unreplaced placeholders
        placeholders = ["{{CANDIDATE_NAME}}", "{{CANDIDATE_EMAIL}}", "{{CANDIDATE_LOCATION_FROM_PROFILE}}", "{{CONTACT_INFO}}"]
        found_placeholders = [p for p in placeholders if p in cv_json]
        
        if found_placeholders:
            report.add_warning(f"Found unreplaced placeholders: {found_placeholders}")
        
        # Check for duplicate bullets (simple check)
        roles = self._extract_roles(cv_data)
        for role in roles:
            bullets = role.get("bullets", [])
            if bullets and isinstance(bullets[0], dict):
                bullet_texts = [b.get("content", "") for b in bullets if b.get("content")]
            else:
                bullet_texts = [b for b in bullets if b]
            
            unique_bullets = set(bullet_texts)
            if len(unique_bullets) < len(bullet_texts):
                duplicates = len(bullet_texts) - len(unique_bullets)
                report.add_warning(f"Role '{role.get('company')}' has {duplicates} duplicate bullets")
    
    def _add_profile_metrics(
        self,
        profile_roles: List[Dict[str, Any]],
        cv_roles: List[Dict[str, Any]],
        report: CVQualityReport
    ):
        """Add metrics about profile size for context."""
        report.add_metric("profile_size", self._categorize_profile_size(len(profile_roles)))
        report.add_metric("profile_total_years", self._calculate_total_years(profile_roles))
        
        # Calculate compression ratio
        profile_bullets = sum(len(r.get("description", [])) for r in profile_roles)
        cv_bullets = sum(len(r.get("bullets", [])) for r in cv_roles)
        
        if profile_bullets > 0:
            compression_ratio = round((cv_bullets / profile_bullets) * 100, 1)
            report.add_metric("bullet_compression_pct", compression_ratio)
            
            if compression_ratio < 30:
                report.add_warning(f"High compression: only {compression_ratio}% of original bullets retained")
            elif compression_ratio > 90:
                report.add_warning(f"Low compression: {compression_ratio}% of original bullets retained (may be too verbose)")
    
    # ========== PRIVATE AUTO-CORRECTION METHODS ==========
    
    def _add_missing_roles(
        self,
        cv_roles: List[Dict[str, Any]],
        profile_roles: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Add missing roles from profile to CV with basic formatting."""
        cv_companies = {self._normalize_company(r.get("company", "")) for r in cv_roles}
        added_count = 0
        
        for profile_role in profile_roles:
            company_name = self._normalize_company(profile_role.get("company_name", ""))
            
            if company_name not in cv_companies:
                # Create a basic role entry from profile
                basic_role = {
                    "company": profile_role.get("company_name", "Unknown Company"),
                    "title": profile_role.get("job_title", "Unknown Title"),
                    "start_date": profile_role.get("start_date", ""),
                    "end_date": profile_role.get("end_date", "Present"),
                    "bullets": profile_role.get("description", [])[:3],  # Take first 3 bullets
                    "location": profile_role.get("location", "")
                }
                
                # Remove location if empty
                if not basic_role["location"]:
                    del basic_role["location"]
                
                cv_roles.append(basic_role)
                cv_companies.add(company_name)
                added_count += 1
                logger.info(f"[CV AUTO-CORRECT] Added missing role: {basic_role['company']}")
        
        return cv_roles, added_count
    
    def _ensure_minimum_bullets(
        self,
        cv_roles: List[Dict[str, Any]],
        profile_roles: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Ensure each role has minimum bullet count by pulling from profile."""
        current_year = datetime.now().year
        fixed_count = 0
        
        # Create profile lookup by company
        profile_lookup = {
            self._normalize_company(r.get("company", "")): r
            for r in profile_roles
        }
        
        for role in cv_roles:
            company = self._normalize_company(role.get("company", ""))
            bullets = role.get("bullets", [])
            
            # Handle object array format
            if bullets and isinstance(bullets[0], dict):
                bullets = [b.get("content", "") for b in bullets if b.get("content")]
                role["bullets"] = bullets
            
            # Determine minimum based on recency
            is_recent = self._is_recent_role(role.get("start_date", ""), current_year)
            min_bullets = self.min_bullets_recent_roles if is_recent else self.min_bullets_older_roles
            
            if len(bullets) < min_bullets and company in profile_lookup:
                # Pull additional bullets from profile
                profile_role = profile_lookup[company]
                profile_bullets = profile_role.get("description", [])
                
                # Add bullets until we hit minimum
                bullets_needed = min_bullets - len(bullets)
                additional_bullets = [b for b in profile_bullets if b not in bullets][:bullets_needed]
                
                if additional_bullets:
                    role["bullets"].extend(additional_bullets)
                    fixed_count += 1
                    logger.info(f"[CV AUTO-CORRECT] Added {len(additional_bullets)} bullets to {role.get('company')}")
        
        return cv_roles, fixed_count
    
    def _sort_roles_chronologically(
        self,
        cv_roles: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Sort roles in reverse chronological order."""
        if len(cv_roles) < 2:
            return cv_roles, False
        
        original_order = [r.get("company") for r in cv_roles]
        
        sorted_roles = sorted(
            cv_roles,
            key=lambda r: self._parse_date_for_sort(r.get("start_date", "")),
            reverse=True
        )
        
        new_order = [r.get("company") for r in sorted_roles]
        was_sorted = original_order != new_order
        
        return sorted_roles, was_sorted
    
    # ========== HELPER METHODS ==========
    
    def _normalize_company(self, company: str) -> str:
        """Normalize company name for comparison."""
        return company.lower().strip().replace("ltd.", "").replace("ltd", "").replace(".", "").strip()
    
    def _is_recent_role(self, start_date: str, current_year: int) -> bool:
        """Check if a role is recent (within threshold years)."""
        if not start_date:
            return False
        
        try:
            # Extract year from various formats
            import re
            year_match = re.search(r'\d{4}', start_date)
            if year_match:
                year = int(year_match.group())
                return (current_year - year) <= self.recent_years_threshold
        except Exception:
            pass
        
        return False
    
    def _parse_date_for_sort(self, date_str: str) -> Tuple[int, int]:
        """Parse date string to (year, month) tuple for sorting."""
        if not date_str or date_str.lower() == "present":
            return (9999, 12)
        
        import re
        
        # Try to extract year
        year_match = re.search(r'\d{4}', date_str)
        if not year_match:
            return (0, 0)
        
        year = int(year_match.group())
        
        # Try to extract month
        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
        }
        
        month = 6  # Default to mid-year
        for month_name, month_num in month_map.items():
            if month_name in date_str.lower():
                month = month_num
                break
        
        return (year, month)
    
    def _categorize_profile_size(self, role_count: int) -> str:
        """Categorize profile by size."""
        if role_count <= 3:
            return "small"
        elif role_count <= 8:
            return "medium"
        elif role_count <= 15:
            return "large"
        else:
            return "very_large"
    
    def _calculate_total_years(self, profile_roles: List[Dict[str, Any]]) -> int:
        """Calculate approximate total years of experience."""
        # Simple calculation based on role count
        # More sophisticated version would parse actual dates
        return len(profile_roles) * 2  # Rough estimate

