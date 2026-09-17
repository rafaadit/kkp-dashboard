<div class="login-wrap">
  <form class="login card" method="post" action="/login">
    <h1><?= \KKP\View::e($config->appName); ?></h1>
    <p class="muted">Masuk untuk mengakses Market Intelligence &amp; EXIM Automation</p>
    <label>Email</label>
    <input type="email" name="email" value="<?= \KKP\View::e($email ?? ''); ?>" required autofocus>
    <label>Password</label>
    <input type="password" name="password" required>
    <button class="btn btn-primary" type="submit">Masuk</button>
  </form>
</div>