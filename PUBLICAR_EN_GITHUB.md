# Publicar en GitHub (aceleradora-la)

El código está commiteado y el remote configurado. Falta crear el repositorio en GitHub.

## Pasos

1. **Crear el repositorio en GitHub**
   - Entrá a https://github.com/organizations/aceleradora-la/repositories/new  
     (o https://github.com/new si es tu usuario)
   - **Repository name:** `odoo-fund-expedientes`
   - Dejalo **vacío** (sin README, sin .gitignore).
   - Crear el repositorio.

2. **Publicar**
   Desde la carpeta del proyecto (`c:\Users\ignac\expedientes`):

   ```bash
   git push -u origin master
   ```

   Si en la organización usan la rama `main` por defecto, podés renombrar y subir así:

   ```bash
   git branch -M main
   git push -u origin main
   ```

3. **URL del repo (después de crearlo)**  
   https://github.com/aceleradora-la/odoo-fund-expedientes
