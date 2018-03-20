async function laterInMs(delay) {
  return new Promise(function(resolve) {
    setTimeout(resolve, delay);
  });
}


module.exports = {laterInMs: laterInMs}
