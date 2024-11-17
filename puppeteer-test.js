#! /usr/bin/env node
const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: false });
  const page = await browser.newPage();

  // Navigate to your page
  await page.goto('http://localhost:5555/templates/new'); // Replace with the actual URL where the form is hosted

  // Fill out the initial inputs
  await page.type('input[name="template_name"]', 'Example Template');
  await page.type('input[name="entry_path_template"]', '/example/path');
  await page.type('input[name="neocities_path"]', '/neocities/example');

  // Add a new field
  await page.click('#new-field');

  // Fill out the new field's inputs
  const fieldSelector = '.fieldinput:not(.hidden)';
  await page.type(`${fieldSelector} input[name="field_name"]`, 'Example Field Name');
  await page.select(`${fieldSelector} select[name="field_type"]`, 'text');

  // Fill out the text areas
  await page.type('textarea[name="index_template"]', '<h1>Index Template Content</h1>');
  await page.type('textarea[name="entry_template"]', '<p>Entry Template Content</p>');

  // Submit the form
  await page.click('input[type="submit"]');

  // Wait for the form submission to complete (you can add navigation or specific checks here if needed)
  await page.waitForNavigation();

  const exampleTemplateName = 'Example Template';
  const pageContent = await page.content();
  if (!pageContent.includes(exampleTemplateName)) {
    console.error(`Text "${exampleTemplateName}" not found on the page.`);
  }

  /*************************
   * UPDATE TEMPLATE
   *************************/

  // Click the template name "Example Template"
  const linkClicked = await page.evaluate(() => {
      const link = Array.from(document.querySelectorAll('a')).find(a => a.textContent.trim() === 'Example Template');
      link.click();
  });

  // Wait for navigation to the update form
  await page.waitForNavigation();

  // Clear the template name field
  await page.waitForSelector('input[name="templateName"]'); // Adjust to the actual selector
  await page.evaluate(() => {
      document.querySelector('input[name="templateName"]').value = '';
  });

  const newTemplateName = 'New Template Name';
  await page.type('input[name="templateName"]', newTemplateName);

  await page.click('button[type="submit"]'); // Adjust to the actual selector

  await page.waitForNavigation();

  if (!await page.content().includes(newTemplateName)) {
    console.error(`Text "${newTemplateName}" not found on the page.`);
  }

  await browser.close();
})();
