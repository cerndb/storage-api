Summary: CERN Unified Storage API
Name: storage-api
Version: 1.1.0
Release: 1%{?dist}
Source0: %{name}-%{version}.tar.gz
License: GPLv3
Group: CERN/Utilities
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
BuildArch: noarch
Requires: python34-devel python34-setuptools python34-pip python-virtualenv >= 15.1.0 gcc
Vendor: Albin Stjerna <albin.stjerna@cern.ch>
Url: https://github.com/cerndb/storage-api

%define __os_install_post %{nil}

%description
A unified REST API for CERNs storage back-ends.

%prep
%setup -q -n %{name}-%{version} -n %{name}-%{version}

%install
mkdir -p $RPM_BUILD_ROOT/opt/apps/storage-api/
cp -arv ./. $RPM_BUILD_ROOT/opt/apps/storage-api/
rm -rfv $RPM_BUILD_ROOT/opt/apps/storage-api/{html,deploy.sh,deploy_key.enc,*.tar.gz,swagger.json,*.spec,build,dist}

%post
cd /opt/apps/storage-api/
virtualenv -p python3 storage-venv
source storage-venv/bin/activate
pip install -r requirements.txt
python setup.py install

%postun
rm -rf /opt/apps/storage-api

%clean
rm -rf $RPM_BUILD_ROOT

%files
/opt/apps/storage-api/
%defattr(-,root,root)
