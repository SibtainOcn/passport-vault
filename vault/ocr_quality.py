"""Approval gate for machine-extracted fields. No Excel-based OCR correction."""

def apply_quality_gate(verification, status, extraction):
    extraction = extraction if isinstance(extraction, dict) else {}
    quality = extraction.get('ocr_quality') or {}
    confidence = quality.get('fields') or {}
    reasons = []
    if extraction.get('multiple_identities'):
        reasons.append('Multiple passport identities require review.')
    if status == 'failed':
        # Not-found can be final only when the number itself is reliably read.
        if confidence.get('passport_number', {}).get('trusted') is not True:
            reasons.append('Passport number has no trusted OCR evidence; not-found is provisional.')
    elif status == 'approved':
        required = ('passport_number','dob','gender','date_of_issue','date_of_expiry')
        uncertain = sorted(f for f in required if confidence.get(f, {}).get('trusted') is not True)
        if uncertain:
            reasons.append('OCR confirmation required: ' + ', '.join(uncertain))
        if quality.get('review_required', True):
            reasons.extend(quality.get('reasons') or ['OCR quality evidence is missing or requires review.'])
    if reasons:
        verification = dict(verification)
        verification['comparison_status_before_quality_gate'] = status
        verification['status'] = 'review'
        verification['reason'] = ' '.join(dict.fromkeys(reasons))
        verification['ocr_review_reasons'] = list(dict.fromkeys(reasons))
        return verification, 'review'
    return verification, status
