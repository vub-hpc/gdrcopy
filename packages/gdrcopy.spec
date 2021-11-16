%{!?_release: %define _release 1}
%{!?GDR_VERSION: %define GDR_VERSION 2.0}
%{!?KVERSION: %define KVERSION %(uname -r)}
%{!?MODULE_LOCATION: %define MODULE_LOCATION /kernel/drivers/misc/}
%{!?NVIDIA_DRIVER_VERSION: %define NVIDIA_DRIVER_VERSION UNKNOWN}
%{!?NVIDIA_SRC_DIR: %define NVIDIA_SRC_DIR UNDEFINED}
%{!?BUILD_KMOD: %define BUILD_KMOD 0}
%global debug_package %{nil}
%global krelver %(echo -n %{KVERSION} | sed -e 's/-/_/g')
%define MODPROBE %(if ( /sbin/modprobe -c | grep -q '^allow_unsupported_modules  *0'); then echo -n "/sbin/modprobe --allow-unsupported-modules"; else echo -n "/sbin/modprobe"; fi )
%define usr_src_dir /usr/src

# For DKMS, dynamic
%define dkms_kernel_version $(uname -r)
# For kmod, static
%define kmod_kernel_version %{KVERSION}

%define kernel_version %{dkms_kernel_version}
%define old_driver_install_dir /lib/modules/%{kernel_version}/%{MODULE_LOCATION}

# Use the same name scheme as for the Nvidia Drivers
# KMOD package has 'kmod' as static name
%global kmod_fullname kmod
# DKMS package has an extra 'dkms' suffix
%global dkms %{kmod_fullname}-dkms


%define gdrdrv_install_script                                           \
/sbin/depmod -a %{kernel_version} &> /dev/null ||:                      \
%{MODPROBE} -rq gdrdrv||:                                               \
%{MODPROBE} gdrdrv||:                                                   \
                                                                        \
if ! ( /sbin/chkconfig --del gdrcopy > /dev/null 2>&1 ); then           \
   true                                                                 \
fi                                                                      \
                                                                        \
/sbin/chkconfig --add gdrcopy                                           \
                                                                        \
service gdrcopy start                                                    


%global dkms_install_script                                             \
echo "Start gdrcopy-kmod installation."                                 \
dkms add -m gdrdrv -v %{version} -q --rpm_safe_upgrade || :             \
                                                                        \
# Rebuild and make available for all installed kernel                   \
echo "Building and installing to all available kernels."                \
echo "This process may take a few minutes ..."                          \
for kver in $(ls -1d /lib/modules/* | cut -d'/' -f4)                    \
do                                                                      \
    dkms build -m gdrdrv -v %{version} -k ${kver} -q || :               \
    dkms install -m gdrdrv -v %{version} -k ${kver} -q --force || :     \
done                                                                    \
                                                                        \
%define kernel_version %{dkms_kernel_version}                           \
%{gdrdrv_install_script}


%global daemon_reload_script                                            \
if [ -e /usr/bin/systemctl ]; then                                      \
    /usr/bin/systemctl daemon-reload                                    \
fi


Name:           gdrcopy
Version:        %{GDR_VERSION}
Release: 	%{krelver}.%{_release}%{?dist}
Summary:        GDRcopy library and companion kernel-mode driver    
Group:          System Environment/Libraries
License:        MIT
URL:            https://github.com/NVIDIA/gdrcopy
Source0:        %{name}-%{version}.tar.gz
BuildRequires:  gcc kernel-headers check-devel
Requires:       check

%package devel
Summary: The development files
Group: System Environment/Libraries
Requires: %{name} = %{version}-%{_release}%{?dist}
BuildArch: noarch

%if %{BUILD_KMOD} == 0
%package %{dkms}
Summary: The kernel-mode driver
Group: System Environment/Libraries
Requires: dkms >= 1.00
Requires: bash
Release: %{NVIDIA_DRIVER_VERSION}.%{krelver}.%{_release}%{?dist}dkms
BuildArch: noarch
Provides: %{name}-kmod = %{version}-%{_release}
%if 0%{?rhel} >= 8
# Recommends tag is a weak dependency, whose support started in RHEL8.
# See https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/packaging_and_distributing_software/new-features-in-rhel-8_packaging-and-distributing-software#support-for-weak-dependencies_new-features-in-rhel-8.
Recommends: kmod-nvidia-latest-dkms
%endif

%else
# This is the real kmod package, which contains prebuilt gdrdrv.ko.
%package %{kmod_fullname}
Summary: The kernel-mode driver
Group: System Environment/Libraries
Release: %{NVIDIA_DRIVER_VERSION}.%{krelver}.%{_release}%{?dist}
Provides: %{name}-kmod = %{version}-%{_release}

%endif


%description
GDRCopy, a low-latency GPU memory copy library and a kernel-mode driver, built on top of the 
NVIDIA GPUDirect RDMA technology.

%description devel
GDRCopy, a low-latency GPU memory copy library and a kernel-mode driver, built on top of the 
NVIDIA GPUDirect RDMA technology.

%if %{BUILD_KMOD} == 0
%description %{dkms}
Kernel-mode driver for GDRCopy with DKMS support.
%else
%description %{kmod_fullname}
Kernel-mode driver for GDRCopy built for GPU driver %{NVIDIA_DRIVER_VERSION} and Linux kernel %{KVERSION}.
%endif

%prep
%setup

%build
echo "building"
make -j8 config lib
%if %{BUILD_KMOD} > 0
make -j8 NVIDIA_SRC_DIR=%{NVIDIA_SRC_DIR} driver
%endif

%install
# Install gdrcopy library
make lib_install DESTDIR=$RPM_BUILD_ROOT prefix=%{_prefix} libdir=%{_libdir}

%if %{BUILD_KMOD} > 0
# Install gdrdrv driver
make drv_install DESTDIR=$RPM_BUILD_ROOT NVIDIA_SRC_DIR=%{NVIDIA_SRC_DIR}
%endif

# Install gdrdrv src
mkdir -p $RPM_BUILD_ROOT%{usr_src_dir}
mkdir -p $RPM_BUILD_ROOT%{usr_src_dir}/gdrdrv-%{version}
cp -a $RPM_BUILD_DIR/%{name}-%{version}/src/gdrdrv/gdrdrv.c $RPM_BUILD_ROOT%{usr_src_dir}/gdrdrv-%{version}/
cp -a $RPM_BUILD_DIR/%{name}-%{version}/src/gdrdrv/gdrdrv.h $RPM_BUILD_ROOT%{usr_src_dir}/gdrdrv-%{version}/
cp -a $RPM_BUILD_DIR/%{name}-%{version}/src/gdrdrv/Makefile $RPM_BUILD_ROOT%{usr_src_dir}/gdrdrv-%{version}/
cp -a $RPM_BUILD_DIR/%{name}-%{version}/src/gdrdrv/nv-p2p-dummy.c $RPM_BUILD_ROOT%{usr_src_dir}/gdrdrv-%{version}/

%if %{BUILD_KMOD} == 0
cp -a $RPM_BUILD_DIR/%{name}-%{version}/dkms.conf $RPM_BUILD_ROOT%{usr_src_dir}/gdrdrv-%{version}
%endif

# Install gdrdrv service script
install -d $RPM_BUILD_ROOT/etc/init.d
install -m 0755 $RPM_BUILD_DIR/%{name}-%{version}/packages/rhel/init.d/gdrcopy $RPM_BUILD_ROOT/etc/init.d

%if %{BUILD_KMOD} == 0
%post %{dkms}
if [ "$1" == "2" ] && [ -e "%{old_driver_install_dir}/gdrdrv.ko" ]; then
    echo "Old package is detected. Defer installation until after the old package is removed."

    # Prevent the uninstall scriptlet of the old package complaining about change in gdrcopy service
    %{daemon_reload_script}

    exit 0;
fi

# Prevent race with kmod-nvidia-latest-dkms triggerin
if [ ! -e "%{_localstatedir}/lib/rpm-state/gdrcopy-dkms/installed" ]; then
    %{dkms_install_script}
    mkdir -p %{_localstatedir}/lib/rpm-state/gdrcopy-dkms
    touch %{_localstatedir}/lib/rpm-state/gdrcopy-dkms/installed
fi

%else
%post %{kmod_fullname}
%define kernel_version %{kmod_kernel_version}
%{gdrdrv_install_script}

%endif


%if %{BUILD_KMOD} == 0
%preun %{dkms}
service gdrcopy stop||:
%{MODPROBE} -rq gdrdrv||:
if ! ( /sbin/chkconfig --del gdrcopy > /dev/null 2>&1 ); then
   true
fi              

# Remove all versions from DKMS registry
echo "Uninstalling and removing the driver."
echo "This process may take a few minutes ..."
dkms uninstall -m gdrdrv -v %{version} -q --all || :
dkms remove -m gdrdrv -v %{version} -q --all --rpm_safe_upgrade || :

# Clean up the weak-updates symlinks
find /lib/modules/*/weak-updates -name "gdrdrv.ko.*" -delete &> /dev/null || :
find /lib/modules/*/weak-updates -name "gdrdrv.ko" -delete &> /dev/null || :

%else
%preun %{kmod_fullname}
service gdrcopy stop||:
%{MODPROBE} -rq gdrdrv||:
if ! ( /sbin/chkconfig --del gdrcopy > /dev/null 2>&1 ); then
   true
fi              

%endif

%if %{BUILD_KMOD} == 0
%postun %{dkms}
%{daemon_reload_script}

%triggerpostun %{dkms} -- gdrcopy-kmod <= 2.1-1
%{dkms_install_script}

%triggerin %{dkms} -- kmod-nvidia-latest-dkms
if [ "$1" == "2" ] && [ -e "%{old_driver_install_dir}/gdrdrv.ko" ]; then
    echo "kmod-nvidia-latest-dkms is detected but defer installation because of the old gdrcopy-kmod package."
    exit 0;
fi

# Prevent race with post
if [ ! -e "%{_localstatedir}/lib/rpm-state/gdrcopy-dkms/installed" ]; then
    %{dkms_install_script}
    mkdir -p %{_localstatedir}/lib/rpm-state/gdrcopy-dkms
    touch %{_localstatedir}/lib/rpm-state/gdrcopy-dkms/installed
fi

%triggerun %{dkms} -- kmod-nvidia-latest-dkms
# This dkms package has only weak dependency with kmod-nvidia-latest-dkms, which is not enforced by RPM.
# Uninstalling kmod-nvidia-latest-dkms would not result in uninstalling this package.
# However, gdrdrv may prevent the removal of nvidia.ko.
# Hence, we rmmod gdrdrv before starting kmod-nvidia-latest-dkms uninstallation.
service gdrcopy stop||:
%{MODPROBE} -rq gdrdrv||:
service gdrcopy start > /dev/null 2>&1 ||:

%posttrans %{dkms}
# Cleaning up
if [ -e "%{_localstatedir}/lib/rpm-state/gdrcopy-dkms/installed" ]; then
    rm -f %{_localstatedir}/lib/rpm-state/gdrcopy-dkms/installed
fi

%else
%postun %{kmod_fullname}
%{daemon_reload_script}

%endif


%clean
rm -rf $RPM_BUILD_DIR/%{name}-%{version}
[ "x$RPM_BUILD_ROOT" != "x" ] && rm -rf $RPM_BUILD_ROOT


%files
# Executables are disabled
# %{_prefix}/bin/apiperf
# %{_prefix}/bin/copybw
# %{_prefix}/bin/copylat
# %{_prefix}/bin/sanity
%{_libdir}/libgdrapi.so.?.?
%{_libdir}/libgdrapi.so.?
%{_libdir}/libgdrapi.so


%files devel
%{_prefix}/include/gdrapi.h
%doc README.md


%if %{BUILD_KMOD} == 0
%files %{dkms}
%defattr(-,root,root,-)
/etc/init.d/gdrcopy
%{usr_src_dir}/gdrdrv-%{version}/gdrdrv.c
%{usr_src_dir}/gdrdrv-%{version}/gdrdrv.h
%{usr_src_dir}/gdrdrv-%{version}/Makefile
%{usr_src_dir}/gdrdrv-%{version}/nv-p2p-dummy.c

%{usr_src_dir}/gdrdrv-%{version}/dkms.conf

%else
%files %{kmod_fullname}
%defattr(-,root,root,-)
/etc/init.d/gdrcopy
%{usr_src_dir}/gdrdrv-%{version}/gdrdrv.c
%{usr_src_dir}/gdrdrv-%{version}/gdrdrv.h
%{usr_src_dir}/gdrdrv-%{version}/Makefile
%{usr_src_dir}/gdrdrv-%{version}/nv-p2p-dummy.c

%{old_driver_install_dir}/gdrdrv.ko

%endif


%changelog
* Tue Nov 16 2021 Alex Domingo <alex.domingo.toro@vub.be> 2.3-0
- Roll back name scheme to static package names
- Disable DKMS module on KMOD builds
- Remove (again) exes from gdrcopy and dependency on CUDA
* Fri Jul 23 2021 Pak Markthub <pmarkthub@nvidia.com> %{GDR_VERSION}-%{_release}
- Remove automatically-generated build id links.
- Remove gdrcopy-kmod from the Requires field.
- Add apiperf test.
- Various updates in README.
- Revamp gdrdrv to fix race-condition bugs.
* Fri May 07 2021 Alex Domingo <alex.domingo.toro@vub.be> %{GDR_VERSION}-%{_release}
- Remove package signing
- Remove exes from gdrcopy and dependency on CUDA
- Fix install step of non-dkms kmod
* Mon Feb 01 2021 Pak Markthub <pmarkthub@nvidia.com> 2.2-1
- Add support for ARM64.
- Update various information on README.
- Improve Makefile.
- Add multi-arch support.
- Handle removal of HAVE_UNLOCKED_IOCTL in Linux kernel v5.9 and later.
- Prevent dpkg package creation to unnecessarily compile gdrdrv.
- Improve gdr_open error message.
- Fix bug that prevents sanity from correctly summarizing failure.
- Add dkms support in kmod package.
- Handle the removal of kzfree in Linux kernel v5.10 and later.
- Improve small-size copy-to-mapping.
* Mon Jan 18 2021 Pak Markthub <pmarkthub@nvidia.com> 2.1-2
- Add DKMS support in gdrcopy-kmod.rpm
* Fri Jul 31 2020 Davide Rossetti <drossetti@nvidia.com> 2.1-1
- fix build problem on RHL8 kernels
- relax checks in gdrdrv to support multi-threading use cases
- fix fd leak in gdr_open()
* Mon Mar 02 2020 Davide Rossetti <drossetti@nvidia.com> 2.0-4
- Introduce copylat test application.
- Introduce basic_with_tokens and invalidation_fork_child_gdr_pin_parent_with_tokens sub-tests in sanity.
- Remove the dependency with libcudart.so.
- Clean up the code in the tests folder.
- Change the package maintainer to Davide Rossetti.
* Mon Sep 16 2019 Pak Markthub <pmarkthub@nvidia.com> 2.0-3
- Harden security in gdrdrv.
- Enable cached mappings in POWER9.
- Improve copy performance with unrolling in POWERPC.
- Creates _sanity_ unit test for testing the functionality and security.
- Consolidate basic and _validate_ into sanity unit test.
- Introduce compile time and runtime version checking in libgdrapi.
- Improve rpm packaging.
- Introduce deb packaging for the userspace library and the applications.
- Introduce dkms packaging for the gdrdrv driver.
- Rename gdr_copy_from/to_bar to gdr_copy_from/to_mapping.
- Update README
* Thu Jul 26 2018 Davide Rossetti <davide.rossetti@gmail.com> 1.4-2
- bumped minor version
* Fri Jun 29 2018 Davide Rossetti <davide.rossetti@gmail.com> 1.3-2
- a few bug fixes
* Mon Feb 13 2017 Davide Rossetti <davide.rossetti@gmail.com> 1.2-2
- package libgdrcopy.so as well
- add basic test
* Thu Sep 15 2016 Davide Rossetti <davide.rossetti@gmail.com> 1.2-1
- First version of RPM spec

