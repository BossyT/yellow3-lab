'use strict';
// GET /api/auth/logout -> clear the session cookie and return to the gateway.
const { cookie } = require('../_lib/util');

module.exports = async (req, res) => {
  res.setHeader('Set-Cookie', cookie('y3mi', '', 0));
  res.writeHead(302, { Location: '/research/model-adoption' });
  res.end();
};
