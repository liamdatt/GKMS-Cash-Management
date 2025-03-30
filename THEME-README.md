# GKMS Cash Management System - Theme Documentation

## Theme Colors

The GKMS Cash Management System uses a consistent red, black, and white color theme across all pages:

### Primary Colors
- **Primary Red:** `#E50914`
- **Dark Red:** `#B71C1C`
- **Bright Red:** `#FF3B30`
- **Black:** `#212529`
- **White:** `#FFFFFF`

### CSS Variables

The theme colors are defined as CSS variables in `modern-theme.css`:

```css
:root {
  --primary: #E50914;
  --primary-light: #FF3B30;
  --secondary: #B71C1C;
  --success: #28a745;
  --danger: #dc3545;
  --warning: #ffc107;
  --info: #17a2b8;
  --light: #f8f9fa;
  --dark: #212529;
}
```

## UI Components

The theme includes styled components for consistent UI across the application:

1. **Cards** - Use the `.modern-card` class with `.modern-card-header` and `.modern-card-body`
2. **Buttons** - Use `.btn-modern` with `.btn-modern-primary` or other variants
3. **Tables** - Use `.table-modern` for consistently styled tables
4. **Forms** - Use `.form-control-modern` and `.form-label-modern` for form controls
5. **Modals** - Apply `.modal-modern` to modals
6. **Badges** - Use `.badge-modern` with status variants

## Gradients

Gradients are used for visual interest:

- Primary gradient: `linear-gradient(45deg, #E50914, #FF3B30)`
- Secondary gradient: `linear-gradient(45deg, #B71C1C, #E50914)`

## Future Improvements

Potential future theme improvements:
- Custom illustrations that match the color theme
- Animated transitions between pages
- Dark mode toggle
 