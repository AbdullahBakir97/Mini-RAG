<template>
  <div class="not-found">
    <p class="code mono">404</p>
    <h1>Page not found</h1>
    <p class="muted">The page does not exist, or the project name is not valid.</p>
    <RouterLink to="/" class="btn btn-primary">Back to projects</RouterLink>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 70vh;
  padding: 24px;
  text-align: center;
}

.code {
  color: var(--accent);
  font-size: 14px;
  font-weight: 600;
}

.btn {
  margin-top: 8px;
}
</style>
