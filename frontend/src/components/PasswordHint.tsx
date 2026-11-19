// Same rules as the backend (validate_password_strength + length 8-128).
export function PasswordHint() {
  return (
    <span className="hint">
      Від 8 символів: велика й мала латинська літера (A–Z, a–z), цифра та спецсимвол.
    </span>
  )
}
