// FormData.get() returns string | File | null; text fields are always strings.
export function formText(form: FormData, name: string): string {
  const value = form.get(name)
  return typeof value === 'string' ? value.trim() : ''
}
