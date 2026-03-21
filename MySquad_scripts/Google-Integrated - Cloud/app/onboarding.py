"""
Responsibility: Onboarding business logic.
Handles user profile creation during onboarding session.
"""

import uuid
from app.db import get_db_connection
from app.logger import setup_logger
from app.schemas import OnboardingRequest

logger = setup_logger(__name__)


def create_onboarding_user(payload: OnboardingRequest) -> tuple[bool, str]:
    """
    Create a new user during onboarding.
    
    Args:
        payload: OnboardingRequest with user data
        
    Returns:
        Tuple of (success: bool, message: str)
        Success if user created, fails on error
    """
    try:
        # Extract and format data
        user_id = str(uuid.uuid4())  # Generate unique user_id for new user
        phone_no = payload.user.phone_no
        full_name = f"{payload.user.firstName} {payload.user.lastName}"
        username = payload.user.userName
        email = payload.user.email
        # Extract values from primaryFocus dict
        interests = ",".join(payload.builderProfile.primaryFocus.values())
        help_needs = ",".join(payload.helpNeeds)

        # Attempt to insert new user
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            try:
                # Insert user and get result
                cur.execute("""
                    INSERT INTO myguy_users (user_id, phone_no, full_name, username, email, interests, help_needs)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING user_id, username;
                """, (user_id, phone_no, full_name, username, email, interests, help_needs))
                
                # Fetch result before commit
                result = cur.fetchone()
                
                # Commit transaction
                conn.commit()
                
                # Check result
                if result:
                    cur.close()
                    # RealDictCursor returns dict-like objects, access by column name
                    returned_user_id = result['user_id']
                    returned_username = result['username']
                    logger.info(f"Onboarding successful for user: {returned_username}")
                    return True, f"User '{returned_username}' created successfully with user_id: {returned_user_id}"
                else:
                    cur.close()
                    logger.warning(f"Failed to create user: {username}")
                    return False, "Database insert failed - no result returned"
                    
            except Exception as e:
                conn.rollback()
                cur.close()
                error_msg = str(e) if str(e) else repr(e)
                logger.error(f"Database error during onboarding: {error_msg}")
                
                # Provide specific error messages based on database error
                if "duplicate key" in error_msg.lower() or "unique violation" in error_msg.lower():
                    if "email" in error_msg.lower():
                        return False, f"Email '{email}' is already registered"
                    else:
                        return False, f"A user with this email already exists"
                elif "not null violation" in error_msg.lower():
                    return False, "Missing required fields in payload"
                else:
                    return False, f"Database error: {error_msg}"
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Onboarding service error: {error_msg}")
        return False, f"Service error: {error_msg}"

