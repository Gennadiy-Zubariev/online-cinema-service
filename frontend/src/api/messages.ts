// The backend answers in English; the interface is Ukrainian.
// Known messages are translated here, unknown ones are shown as they are.

const EXACT: Record<string, string> = {
  'Invalid email or password.': 'Невірний email або пароль.',
  'Account is not activated. Please check your email.':
    'Акаунт не активовано. Перевірте пошту — ми надіслали посилання.',
  'User with this email already exists.': 'Користувач з таким email уже існує.',
  'Invalid or already used activation token.': 'Посилання активації недійсне або вже використане.',
  'Activation token has expired. Please request a new one.':
    'Посилання активації застаріло. Надішліть нове.',
  'Invalid or expired password reset token. Please request a new one.':
    'Посилання для скидання пароля недійсне або застаріло. Надішліть нове.',
  'Old password is incorrect.': 'Поточний пароль неправильний.',
  'You do not have permission to perform this action.': 'Недостатньо прав для цієї дії.',
  'User not found.': 'Користувача не знайдено.',
  'Movie already purchased.': 'Цей фільм уже придбано — купити його вдруге не можна.',
  'Cart is empty.': 'Корзина порожня.',
  'All movies in the cart are already purchased.': 'Усі фільми з корзини вже придбано.',
  'All movies in the order are already purchased. The order is canceled.':
    'Усі фільми замовлення вже придбано, тому замовлення скасовано.',
  'Order not found.': 'Замовлення не знайдено.',
  'Only pending orders can be paid.': 'Оплатити можна лише неоплачене замовлення.',
  'Image must be a JPEG, PNG or WebP image.': 'Підходять лише зображення JPEG, PNG або WebP.',
  'Replies to replies are not allowed.': 'Відповісти можна лише на коментар, не на відповідь.',
  'Password must contain at least one uppercase letter':
    'Пароль має містити хоча б одну велику літеру.',
  'Password must contain at least one lowercase letter':
    'Пароль має містити хоча б одну малу літеру.',
  'Password must contain at least one digit': 'Пароль має містити хоча б одну цифру.',
  'Password must contain at least one special character':
    'Пароль має містити хоча б один спецсимвол.',
}

const ENTITY_NAMES: Record<string, string> = {
  Movie: 'Фільм',
  Genre: 'Жанр',
  Star: 'Актор',
  Director: 'Режисер',
  Certification: 'Сертифікацію',
  Comment: 'Коментар',
}

export function translateMessage(message: string): string {
  if (message in EXACT) {
    return EXACT[message]
  }
  // "<Entity> not found." / "already exists." / "is in use." from the catalog.
  const match = /^(\w+) (not found|already exists|is in use)\.$/.exec(message)
  if (match && match[1] in ENTITY_NAMES) {
    const entity = ENTITY_NAMES[match[1]]
    if (match[2] === 'not found') return `${entity}: не знайдено.`
    if (match[2] === 'already exists') return `${entity}: такий запис уже існує.`
    return `${entity}: запис використовується, видалити не можна.`
  }
  const size = /^Image must not exceed (\d+) MB\.$/.exec(message)
  if (size) {
    return `Зображення має бути не більше ${size[1]} МБ.`
  }
  return message
}
