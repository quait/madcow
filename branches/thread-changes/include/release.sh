# update __version__ in main bot
# diff trunk from previous release and update ChangeLog
# make a release tag:

release="madcow-1.2.1"

svn copy https://madcow.svn.sourceforge.net/svnroot/madcow/trunk https://madcow.svn.sourceforge.net/svnroot/madcow/tags/$release || exit

# export & make a bundle
svn export https://madcow.svn.sourceforge.net/svnroot/madcow/tags/$release
tar cfjv ${release}.tar.bz2 $release

# upload to anon ftp
rsync -vPazue ssh ${release}.tar.bz2 cj__@frs.sourceforge.net:uploads/

echo "activate release at:"
echo "http://sourceforge.net/project/admin/editpackages.php?group_id=199970"

