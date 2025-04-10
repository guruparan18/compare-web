---
name: "Release Checklist"
about: "Checklist for a release in the Python + AWS + Wagtail/Django project"
title: "[Release] - <Version or Release Name>"
labels: ["release"]
assignees: []
---

# Release Checklist

Use this checklist to ensure all release tasks are completed before deployment.

## 1. Pre-Release

- [ ] **Version Bump**  
  - Confirm/update project version in `setup.py`, `pyproject.toml`, or relevant version file.
  - If you’re using Docker images, ensure the image tags match the new release version.

- [ ] **Changelog**  
  - Update `CHANGELOG.md` (or release notes).  
  - Document all notable changes, bug fixes, and new features.

- [ ] **Dependency Review**  
  - Review Python package dependencies in `requirements.txt` or `Pipfile`.  
  - Update any out-of-date or vulnerable packages.  
  - Ensure requirements are locked to known-good versions if needed.

- [ ] **Tests**  
  - Ensure automated tests (unit/integration) pass (CI should be green).  
  - Check code coverage reports to confirm thresholds are met.  

- [ ] **Lint and Static Analysis**  
  - Confirm code base passes lint checks (flake8, black, isort, etc.).  
  - Fix any warnings or style errors.

## 2. Infrastructure Checks (AWS)

- [ ] **Infrastructure as Code**  
  - If you use Terraform/CloudFormation, ensure the changes for this release have been planned/applied to the correct environment.  
  - Validate no unexpected infrastructure drifts.

- [ ] **Secrets & Environment Variables**  
  - Confirm that any new environment variables required for this release are set (e.g., in AWS SSM Parameter Store, Secrets Manager, or environment configuration).  
  - Double-check that secrets are correctly configured and encrypted.

- [ ] **AWS Services**  
  - If using AWS Lambda, ECR, or ECS, verify that new Docker images or function packages are updated.  
  - For EC2 or ECS-based hosting, ensure the new AMI/image is built and tested.  
  - Check relevant AWS logs (CloudWatch) for errors in staging/pre-production environment.

- [ ] **Scaling/Load Testing** (if relevant)  
  - For major releases or significant changes, run a load test to verify AWS can handle expected traffic.  
  - Review CloudWatch metrics and auto-scaling settings.

## 3. Wagtail / Django-Specific Checks

- [ ] **Migrations**  
  - Run `python manage.py makemigrations` and `python manage.py migrate` in a test environment to ensure database migrations succeed.  
  - Validate backward compatibility if necessary.

- [ ] **Wagtail Pages / CMS Updates**  
  - Confirm that any new page models or content blocks work as expected.  
  - Run through the Wagtail admin to verify new fields or features are functioning.

- [ ] **Static Files**  
  - Check that static files (CSS/JS/images) are collected properly with `collectstatic`.  
  - Confirm the CDN or S3 bucket is serving the correct versions.

- [ ] **Security / Auth**  
  - Verify any new routes or Wagtail admin features are properly permission-protected.  
  - Check that Django’s `ALLOWED_HOSTS`, CSRF settings, and HTTPS configurations are correct.

## 4. Final Confirmation

- [ ] **Documentation**  
  - Update or confirm docs are accurate for new features, changes, or environment instructions (README, wiki, etc.).

- [ ] **Smoke Test in Staging**  
  - Deploy the release candidate to staging/test environment.  
  - Perform a quick end-to-end check on critical paths:
    - User login
    - CRUD operations
    - Wagtail admin usage
    - AWS health checks/logs

- [ ] **Sign Off**  
  - Team lead, QA, or product manager approves the staging/test environment.

## 5. Production Deployment

- [ ] **Scheduled Deployment Window**  
  - Coordinate deployment timing with the team.  
  - Notify stakeholders of any downtime, if applicable.

- [ ] **Tag & Release**  
  - Create a Git tag and GitHub release if using GitHub’s release system.  
  - Publish release notes.

- [ ] **Post-Deployment Checks**  
  - Monitor logs and alerts for issues (e.g., CloudWatch, Sentry, New Relic).  
  - Confirm all services (EC2/ECS, Lambdas, DB) are operating correctly.

- [ ] **Rollback Plan**  
  - Have a rollback or hotfix plan ready if critical issues arise.  
  - Confirm that the previous release version is still deployable if needed.

---

**Additional notes or attachments:**  
<details>
<summary>Optional: Additional context or screenshots</summary>

<!-- Provide any relevant extra context for this release -->

</details>


