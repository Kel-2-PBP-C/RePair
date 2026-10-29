def profile_initials(user):
    initials = "".join(part[0].upper() for part in user.get_full_name().split()[:2])
    return initials or user.get_username()[:2].upper()
